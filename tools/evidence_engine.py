"""LINUM GENESIS: persistent, hash-linked verification evidence."""

import ast
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from memory.database import get_connection, init_db

VALID_RESULTS = frozenset({"PASS", "FAIL", "UNVERIFIED"})

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def initialize_evidence_schema():
    init_db()
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verification_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                validator TEXT NOT NULL,
                result TEXT NOT NULL CHECK(result IN ('PASS', 'FAIL', 'UNVERIFIED')),
                details TEXT NOT NULL,
                duration_ms INTEGER NOT NULL CHECK(duration_ms >= 0),
                previous_hash TEXT NOT NULL,
                evidence_hash TEXT NOT NULL UNIQUE
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_evidence_artifact
            ON verification_evidence(artifact_sha256, id DESC)
        """)
        conn.commit()

def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def calculate_evidence_hash(record):
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()

def record_evidence(artifact, validator, result, details, duration_ms):
    initialize_evidence_schema()
    if result not in VALID_RESULTS:
        raise ValueError(f"Invalid evidence result: {result}")
    
    artifact_hash = hashlib.sha256(artifact.encode("utf-8")).hexdigest()
    details_json = canonical_json(details)

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute("""
            SELECT evidence_hash
            FROM verification_evidence
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        previous_hash = previous[0] if previous else "GENESIS"
        timestamp = utc_now()

        payload = {
            "timestamp": timestamp,
            "artifact_sha256": artifact_hash,
            "validator": validator,
            "result": result,
            "details": json.loads(details_json),
            "duration_ms": int(duration_ms),
            "previous_hash": previous_hash,
        }

        evidence_hash = calculate_evidence_hash(payload)

        cursor = conn.execute("""
            INSERT INTO verification_evidence (
                timestamp, artifact_sha256, validator, result,
                details, duration_ms, previous_hash, evidence_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, artifact_hash, validator, result,
            details_json, int(duration_ms), previous_hash, evidence_hash,
        ))
        evidence_id = cursor.lastrowid
        conn.commit()

    # Preserve the evidence record while exposing the classification API.
    details = payload.get("details", {})
    result = payload.get("result", "UNVERIFIED")

    checks = [details["check"]] if details.get("check") else []
    errors = []

    if result == "FAIL":
        errors.append(details.get("error", "Validation failed"))

    return {
        "id": evidence_id,
        **payload,
        "checks": checks,
        "errors": errors,
        "limitations": [
            "Syntax validation does not establish runtime correctness.",
            "Syntax validation does not establish behavioral correctness.",
            "Syntax validation does not establish security or trustworthiness.",
        ] if payload.get("validator") == "python_ast_parse"
             else ["Validation does not establish overall trustworthiness."],
        "evidence_hash": evidence_hash,
    }

def verify_python_syntax(source):
    started = time.monotonic()
    try:
        ast.parse(source)
        result, details = "PASS", {"check": "python_ast_parse"}
    except SyntaxError as exc:
        result, details = "FAIL", {"check": "python_ast_parse", "line": exc.lineno, "column": exc.offset, "error": exc.msg}
    duration_ms = int((time.monotonic() - started) * 1000)
    return record_evidence(source, "python_ast_parse", result, details, duration_ms)

def verify_evidence_chain():
    initialize_evidence_schema()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, timestamp, artifact_sha256, validator, result, details, duration_ms, previous_hash, evidence_hash
            FROM verification_evidence
            ORDER BY id ASC
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
        if row[7] != expected_previous:
            return {"status": "FAIL", "record_id": row[0], "error": "Previous evidence hash mismatch"}
        if calculate_evidence_hash(record) != row[8]:
            return {"status": "FAIL", "record_id": row[0], "error": "Evidence hash mismatch"}
        expected_previous = row[8]

    return {"status": "PASS", "records_verified": len(rows), "chain_head": expected_previous}
