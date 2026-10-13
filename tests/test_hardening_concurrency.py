import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ConcurrentEvidenceTests(unittest.TestCase):
    def test_serialized_writers_preserve_chain(self):
        project = Path(__file__).resolve().parents[1]

        with tempfile.TemporaryDirectory(prefix="linum-concurrency-") as tmp:
            root = Path(tmp)
            database = root / "evidence.db"

            setup = r'''
import os
import sqlite3

path = os.environ["LINUM_TEST_DB"]

with sqlite3.connect(path) as conn:
    conn.execute("""
        CREATE TABLE verification_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            artifact_sha256 TEXT NOT NULL,
            validator TEXT NOT NULL,
            result TEXT NOT NULL,
            details TEXT NOT NULL,
            duration_ms INTEGER NOT NULL,
            previous_hash TEXT NOT NULL,
            evidence_hash TEXT NOT NULL UNIQUE
        )
    """)
'''

            env = os.environ.copy()
            env["LINUM_TEST_DB"] = str(database)
            env["PYTHONPATH"] = str(project)

            subprocess.run(
                [sys.executable, "-c", setup],
                env=env,
                check=True,
            )

            writer = r'''
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

path = os.environ["LINUM_TEST_DB"]
artifact = sys.argv[1]

def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )

with sqlite3.connect(path, timeout=30) as conn:
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("BEGIN IMMEDIATE")

    row = conn.execute("""
        SELECT evidence_hash
        FROM verification_evidence
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    previous = row[0] if row else "GENESIS"

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "artifact_sha256": hashlib.sha256(
            artifact.encode()
        ).hexdigest(),
        "validator": "concurrency_test",
        "result": "PASS",
        "details": {"check": "concurrent_write"},
        "duration_ms": 0,
        "previous_hash": previous,
    }

    digest = hashlib.sha256(canonical(record).encode()).hexdigest()

    conn.execute("""
        INSERT INTO verification_evidence (
            timestamp, artifact_sha256, validator, result,
            details, duration_ms, previous_hash, evidence_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record["timestamp"],
        record["artifact_sha256"],
        record["validator"],
        record["result"],
        canonical(record["details"]),
        record["duration_ms"],
        previous,
        digest,
    ))

    conn.commit()
'''

            workers = 8
            records_per_worker = 10
            processes = []

            for worker in range(workers):
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        r'''
import subprocess
import sys

code = sys.argv[1]
worker = sys.argv[2]
count = int(sys.argv[3])

for index in range(count):
    subprocess.run(
        [sys.executable, "-c", code, f"{worker}:{index}"],
        check=True,
    )
''',
                        writer,
                        str(worker),
                        str(records_per_worker),
                    ],
                    env=env,
                )
                processes.append(process)

            failures = [
                process.wait()
                for process in processes
                if process.wait() != 0
            ]

            self.assertEqual(failures, [])

            with sqlite3.connect(database) as conn:
                rows = conn.execute("""
                    SELECT id, timestamp, artifact_sha256, validator,
                           result, details, duration_ms, previous_hash,
                           evidence_hash
                    FROM verification_evidence
                    ORDER BY id
                """).fetchall()

            expected_previous = "GENESIS"

            for row in rows:
                record = {
                    "timestamp": row[1],
                    "artifact_sha256": row[2],
                    "validator": row[3],
                    "result": row[4],
                    "details": json.loads(row[5]),
                    "duration_ms": row[6],
                    "previous_hash": row[7],
                }

                self.assertEqual(row[7], expected_previous)

                digest = hashlib.sha256(
                    json.dumps(
                        record,
                        sort_keys=True,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode()
                ).hexdigest()

                self.assertEqual(digest, row[8])
                expected_previous = digest

            self.assertEqual(
                len(rows),
                workers * records_per_worker,
            )

            print(
                f"PASS: {len(rows)} concurrent records; "
                "all hashes and links verified"
            )


if __name__ == "__main__":
    unittest.main()
