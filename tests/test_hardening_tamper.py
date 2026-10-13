import hashlib
import hmac
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.hardening import (
    HardeningError,
    canonical_json,
    create_checkpoint,
    verify_database,
)


class TamperRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(prefix="linum-tamper-")
        self.root = Path(self.tmp_dir.name)
        
        self.db_path = self.root / "evidence.db"
        self.key_path = self.root / "checkpoint.key"
        self.ckpt_path = self.root / "evidence.checkpoint.json"

        self.key_path.write_bytes(b"A" * 32)

        import tools.hardening
        self.original_get_connection = tools.hardening.get_connection
        tools.hardening.get_connection = lambda: sqlite3.connect(str(self.db_path))

        with sqlite3.connect(str(self.db_path)) as conn:
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
            conn.commit()

        self._append_record("artifact_1", "GENESIS")
        self._append_record("artifact_2", self._get_last_hash())

    def tearDown(self):
        import tools.hardening
        tools.hardening.get_connection = self.original_get_connection
        self.tmp_dir.cleanup()

    def _append_record(self, artifact, prev_hash):
        with sqlite3.connect(str(self.db_path)) as conn:
            record = {
                "timestamp": "2026-06-06T00:00:00Z",
                "artifact_sha256": hashlib.sha256(artifact.encode()).hexdigest(),
                "validator": "test",
                "result": "PASS",
                "details": {},
                "duration_ms": 10,
                "previous_hash": prev_hash,
            }
            digest = hashlib.sha256(canonical_json(record).encode()).hexdigest()
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
                canonical_json(record["details"]),
                record["duration_ms"],
                prev_hash,
                digest,
            ))
            conn.commit()

    def _get_last_hash(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute("SELECT evidence_hash FROM verification_evidence ORDER BY id DESC LIMIT 1").fetchone()
            return row[0] if row else "GENESIS"

    def test_deleting_anchored_record(self):
        create_checkpoint(self.ckpt_path, self.key_path)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM verification_evidence WHERE id = 1")
            conn.commit()

        with self.assertRaises(HardeningError):
            verify_database(self.ckpt_path, self.key_path)

    def test_truncating_records_after_checkpoint(self):
        self._append_record("artifact_3", self._get_last_hash())
        create_checkpoint(self.ckpt_path, self.key_path)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM verification_evidence WHERE id = 3")
            conn.commit()

        with self.assertRaises(HardeningError):
            verify_database(self.ckpt_path, self.key_path)

    def test_deleting_intermediate_records(self):
        self._append_record("artifact_3", self._get_last_hash())
        create_checkpoint(self.ckpt_path, self.key_path)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM verification_evidence WHERE id = 2")
            conn.commit()

        with self.assertRaises(HardeningError):
            verify_database(self.ckpt_path, self.key_path)

    def test_modifying_checkpoint_without_key(self):
        create_checkpoint(self.ckpt_path, self.key_path)

        data = json.loads(self.ckpt_path.read_text(encoding="utf-8"))
        data["payload"]["record_id"] = 1
        self.ckpt_path.write_text(json.dumps(data), encoding="utf-8")

        with self.assertRaises(HardeningError):
            verify_database(self.ckpt_path, self.key_path)

    def test_advancing_checkpoint_after_rollback(self):
        create_checkpoint(self.ckpt_path, self.key_path)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM verification_evidence WHERE id = 2")
            conn.commit()

        self._append_record("artifact_fork", self._get_last_hash())

        with self.assertRaises(HardeningError):
            create_checkpoint(self.ckpt_path, self.key_path)


if __name__ == "__main__":
    unittest.main()
