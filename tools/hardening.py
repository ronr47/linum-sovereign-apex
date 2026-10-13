"""LINUM GENESIS: evidence validation, authenticated checkpoints, and isolated execution."""

import argparse
import ast
import hashlib
import hmac
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from memory.database import DB_PATH, get_connection

GENESIS = "GENESIS"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
RESULTS = frozenset({"PASS", "FAIL", "UNVERIFIED"})
REQUIRED_FIELDS = (
    "timestamp",
    "artifact_sha256",
    "validator",
    "result",
    "details",
    "duration_ms",
    "previous_hash",
)


class HardeningError(RuntimeError):
    """Explicit LINUM verification failure."""


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def evidence_digest(record):
    return sha256_text(canonical_json(record))


def validate_record(record, record_id):
    if not isinstance(record, dict):
        raise HardeningError(f"Record {record_id}: expected JSON object")

    if set(record) != set(REQUIRED_FIELDS):
        raise HardeningError(
            f"Record {record_id}: invalid fields; "
            f"expected={sorted(REQUIRED_FIELDS)}, "
            f"actual={sorted(record)}"
        )

    if not isinstance(record["timestamp"], str) or not record["timestamp"]:
        raise HardeningError(f"Record {record_id}: invalid timestamp")

    if not isinstance(record["artifact_sha256"], str):
        raise HardeningError(f"Record {record_id}: invalid artifact hash")

    if not HEX64.fullmatch(record["artifact_sha256"]):
        raise HardeningError(f"Record {record_id}: malformed artifact hash")

    if not isinstance(record["validator"], str) or not record["validator"]:
        raise HardeningError(f"Record {record_id}: invalid validator")

    if record["result"] not in RESULTS:
        raise HardeningError(f"Record {record_id}: invalid result")

    if not isinstance(record["details"], dict):
        raise HardeningError(f"Record {record_id}: details must be an object")

    duration = record["duration_ms"]
    if isinstance(duration, bool) or not isinstance(duration, int) or duration < 0:
        raise HardeningError(f"Record {record_id}: invalid duration_ms")

    previous = record["previous_hash"]
    if not isinstance(previous, str):
        raise HardeningError(f"Record {record_id}: invalid previous_hash")

    if previous != GENESIS and not HEX64.fullmatch(previous):
        raise HardeningError(f"Record {record_id}: malformed previous_hash")


def read_chain(conn):
    columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(verification_evidence)"
        ).fetchall()
    }

    required_columns = {
        "id",
        *REQUIRED_FIELDS,
        "evidence_hash",
    }

    missing = required_columns - columns
    if missing:
        raise HardeningError(
            f"Evidence schema missing columns: {sorted(missing)}"
        )

    rows = conn.execute("""
        SELECT id, timestamp, artifact_sha256, validator,
               result, details, duration_ms, previous_hash, evidence_hash
        FROM verification_evidence
        ORDER BY id ASC
    """).fetchall()

    expected_previous = GENESIS
    records = []

    for row in rows:
        record_id = row[0]

        try:
            details = json.loads(row[5])
        except (TypeError, json.JSONDecodeError) as exc:
            raise HardeningError(
                f"Record {record_id}: malformed details JSON"
            ) from exc

        record = {
            "timestamp": row[1],
            "artifact_sha256": row[2],
            "validator": row[3],
            "result": row[4],
            "details": details,
            "duration_ms": row[6],
            "previous_hash": row[7],
        }

        validate_record(record, record_id)

        if record["previous_hash"] != expected_previous:
            raise HardeningError(
                f"Record {record_id}: previous hash mismatch"
            )

        calculated = evidence_digest(record)

        if not isinstance(row[8], str) or not hmac.compare_digest(
            calculated, row[8]
        ):
            raise HardeningError(
                f"Record {record_id}: evidence hash mismatch"
            )

        expected_previous = calculated
        records.append((record_id, calculated))

    return records


def load_key(key_path):
    path = Path(key_path)

    if not path.is_file():
        raise HardeningError(f"Checkpoint key not found: {path}")

    if path.is_symlink():
        raise HardeningError("Checkpoint key must not be a symbolic link")

    key = path.read_bytes()

    if len(key) < 32:
        raise HardeningError("Checkpoint key must contain at least 32 bytes")

    return key


def checkpoint_mac(payload, key):
    return hmac.new(
        key,
        canonical_json(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def read_checkpoint(path, key):
    checkpoint_path = Path(path)

    if checkpoint_path.is_symlink() or not checkpoint_path.is_file():
        raise HardeningError(
            f"Checkpoint file missing or invalid: {checkpoint_path}"
        )

    try:
        envelope = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HardeningError("Checkpoint file is unreadable or malformed") from exc

    if not isinstance(envelope, dict):
        raise HardeningError("Checkpoint envelope must be an object")

    if set(envelope) != {"payload", "hmac_sha256"}:
        raise HardeningError("Invalid checkpoint envelope fields")

    payload = envelope["payload"]
    supplied_mac = envelope["hmac_sha256"]

    if not isinstance(payload, dict):
        raise HardeningError("Checkpoint payload must be an object")

    if set(payload) != {"version", "record_id", "chain_head"}:
        raise HardeningError("Invalid checkpoint payload fields")

    if payload["version"] != 1:
        raise HardeningError("Unsupported checkpoint version")

    record_id = payload["record_id"]

    if (
        isinstance(record_id, bool)
        or not isinstance(record_id, int)
        or record_id < 0
    ):
        raise HardeningError("Invalid checkpoint record_id")

    chain_head = payload["chain_head"]

    if not isinstance(chain_head, str):
        raise HardeningError("Invalid checkpoint chain_head")

    if record_id == 0:
        if chain_head != GENESIS:
            raise HardeningError("Invalid empty-chain checkpoint")
    elif not HEX64.fullmatch(chain_head):
        raise HardeningError("Malformed checkpoint chain_head")

    expected_mac = checkpoint_mac(payload, key)

    if not isinstance(supplied_mac, str) or not hmac.compare_digest(
        expected_mac, supplied_mac
    ):
        raise HardeningError("Checkpoint authentication failed")

    return payload


def verify_checkpoint(conn, records, checkpoint_path, key):
    payload = read_checkpoint(checkpoint_path, key)
    anchor_id = payload["record_id"]
    anchor_hash = payload["chain_head"]

    if anchor_id == 0:
        if records and records[0][0] <= 0:
            raise HardeningError("Invalid database record ordering")
        if anchor_hash != GENESIS:
            raise HardeningError("Empty-chain anchor mismatch")
    else:
        matching = [
            digest for record_id, digest in records
            if record_id == anchor_id
        ]

        if not matching:
            raise HardeningError(
                "Anchored record missing: possible truncation or rollback"
            )

        if not hmac.compare_digest(matching[0], anchor_hash):
            raise HardeningError(
                "Anchored chain head mismatch: possible tampering"
            )

    return {
        "status": "PASS",
        "records_verified": len(records),
        "anchored_record_id": anchor_id,
        "anchored_chain_head": anchor_hash,
        "current_record_id": records[-1][0] if records else 0,
        "current_chain_head": records[-1][1] if records else GENESIS,
    }


def atomic_write(path, data):
    target = Path(path)
    parent = target.parent

    if not parent.is_dir():
        raise HardeningError(f"Checkpoint directory does not exist: {parent}")

    fd, temporary_name = tempfile.mkstemp(
        prefix=".linum-checkpoint-",
        dir=str(parent),
    )

    temporary = Path(temporary_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary, target)

        directory_fd = os.open(str(parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def create_checkpoint(checkpoint_path, key_path):
    key = load_key(key_path)
    destination = Path(checkpoint_path)

    if destination.is_symlink():
        raise HardeningError("Checkpoint destination must not be a symlink")

    with get_connection() as conn:
        conn.execute("BEGIN")
        records = read_chain(conn)

        if destination.exists():
            old_payload = read_checkpoint(destination, key)
            old_id = old_payload["record_id"]

            if old_id:
                matching = [
                    digest for record_id, digest in records
                    if record_id == old_id
                ]

                if not matching or not hmac.compare_digest(
                    matching[0], old_payload["chain_head"]
                ):
                    raise HardeningError(
                        "Existing checkpoint does not match the database; "
                        "refusing to advance the anchor"
                    )

        record_id, chain_head = (
            records[-1] if records else (0, GENESIS)
        )

        payload = {
            "version": 1,
            "record_id": record_id,
            "chain_head": chain_head,
        }

        envelope = {
            "payload": payload,
            "hmac_sha256": checkpoint_mac(payload, key),
        }

        atomic_write(destination, canonical_json(envelope))
        conn.commit()

    return {
        "status": "PASS",
        "record_id": record_id,
        "chain_head": chain_head,
        "checkpoint": str(destination),
    }


def verify_database(checkpoint_path=None, key_path=None):
    key = load_key(key_path) if checkpoint_path else None

    with get_connection() as conn:
        conn.execute("BEGIN")
        records = read_chain(conn)

        if checkpoint_path:
            result = verify_checkpoint(
                conn, records, checkpoint_path, key
            )
        else:
            result = {
                "status": "PASS",
                "records_verified": len(records),
                "chain_head": records[-1][1] if records else GENESIS,
            }

        conn.commit()

    return result


def classify_python(source):
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return {
            "status": "REJECTED",
            "reason": "SYNTAX_ERROR",
            "line": exc.lineno,
            "column": exc.offset,
            "error": exc.msg,
        }

    return {
        "status": "UNVERIFIED",
        "reason": "SYNTAX_ONLY",
        "behavior_verified": False,
    }


def _limit_child(cpu_seconds, memory_bytes, output_bytes):
    import resource

    resource.setrlimit(
        resource.RLIMIT_CPU,
        (cpu_seconds, cpu_seconds),
    )

    resource.setrlimit(
        resource.RLIMIT_AS,
        (memory_bytes, memory_bytes),
    )

    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (output_bytes, output_bytes),
    )

    resource.setrlimit(
        resource.RLIMIT_CORE,
        (0, 0),
    )

    resource.setrlimit(
        resource.RLIMIT_NOFILE,
        (32, 32),
    )


def execute_python(
    script_path,
    timeout_seconds=5,
    memory_mb=256,
    output_limit=65536,
    args=None,
):
    if os.name != "posix":
        raise HardeningError("Isolated runner requires POSIX")

    script = Path(script_path).resolve(strict=True)

    if not script.is_file():
        raise HardeningError("Script path is not a regular file")

    if not 1 <= timeout_seconds <= 300:
        raise HardeningError("timeout_seconds must be between 1 and 300")

    if not 32 <= memory_mb <= 4096:
        raise HardeningError("memory_mb must be between 32 and 4096")

    if not 1024 <= output_limit <= 1048576:
        raise HardeningError("output_limit must be between 1024 and 1048576")

    argv = [sys.executable, "-I", "-S", str(script)]
    argv.extend(args or [])

    environment = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
    }

    with tempfile.TemporaryDirectory(prefix="linum-run-") as temp:
        stdout_path = Path(temp) / "stdout"
        stderr_path = Path(temp) / "stderr"

        started = time.monotonic()

        with stdout_path.open("wb") as stdout_file, stderr_path.open(
            "wb"
        ) as stderr_file:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=temp,
                env=environment,
                close_fds=True,
                start_new_session=True,
                preexec_fn=lambda: _limit_child(
                    max(1, int(timeout_seconds)),
                    memory_mb * 1024 * 1024,
                    output_limit,
                ),
            )

            timed_out = False

            try:
                return_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True

                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

                process.wait()
                return_code = process.returncode

        elapsed_ms = int((time.monotonic() - started) * 1000)

        stdout_size = stdout_path.stat().st_size
        stderr_size = stderr_path.stat().st_size

        stdout = stdout_path.read_bytes()[:output_limit]
        stderr = stderr_path.read_bytes()[:output_limit]

        if timed_out:
            status = "TIMEOUT"
        elif return_code != 0:
            status = "FAIL"
        else:
            status = "PASS"

        return {
            "status": status,
            "returncode": return_code,
            "timed_out": timed_out,
            "duration_ms": elapsed_ms,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "stdout_bytes": stdout_size,
            "stderr_bytes": stderr_size,
            "output_truncated": (
                stdout_size > output_limit
                or stderr_size > output_limit
            ),
            "limitations": [
                "Resource limits are not a filesystem or network sandbox.",
                "Use an OS sandbox for hostile code.",
            ],
        }


def main():
    parser = argparse.ArgumentParser(
        description="LINUM GENESIS hardening controls"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    checkpoint_parser = subparsers.add_parser("checkpoint")
    checkpoint_parser.add_argument("--path", required=True)
    checkpoint_parser.add_argument("--key-file", required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--checkpoint")
    verify_parser.add_argument("--key-file")

    classify_parser = subparsers.add_parser("classify")
    classify_parser.add_argument("--file", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--file", required=True)
    run_parser.add_argument("--timeout", type=int, default=5)
    run_parser.add_argument("--memory-mb", type=int, default=256)
    run_parser.add_argument("--output-limit", type=int, default=65536)
    run_parser.add_argument("args", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    try:
        if args.command == "checkpoint":
            result = create_checkpoint(args.path, args.key_file)

        elif args.command == "verify":
            if bool(args.checkpoint) != bool(args.key_file):
                raise HardeningError(
                    "--checkpoint and --key-file must be supplied together"
                )

            result = verify_database(args.checkpoint, args.key_file)

        elif args.command == "classify":
            source = Path(args.file).read_text(encoding="utf-8")
            result = classify_python(source)

        elif args.command == "run":
            result = execute_python(
                args.file,
                timeout_seconds=args.timeout,
                memory_mb=args.memory_mb,
                output_limit=args.output_limit,
                args=args.args,
            )

        else:
            raise HardeningError("Unsupported command")

        print(canonical_json(result))

        if result["status"] not in {"PASS", "UNVERIFIED"}:
            return 1

        return 0

    except (
        HardeningError,
        OSError,
        sqlite3.Error,
        ValueError,
    ) as exc:
        print(
            canonical_json({
                "status": "FAIL",
                "error": type(exc).__name__,
                "message": str(exc),
            }),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
