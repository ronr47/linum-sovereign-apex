import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.hardening import (
    HardeningError,
    canonical_json,
    create_checkpoint,
    verify_database,
)


class ChainContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(prefix="linum-continuity-")
        self.root = Path(self.tmp_dir.name)
        
        self.db_path = self.root / "evidence.db"
        self.key_path = self.root / "checkpoint.key"
        self.ckpt_path = self.root / "evidence.checkpoint.json"

        self.key_path.write_bytes(b"B" * 32)

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

        self._append("a1", "GENESIS")
        self._append("a2", self._last_hash())
        self._append("a3", self._last_hash())

    def tearDown(self):
        import tools.hardening
        tools.hardening.get_connection = self.original_get_connection
        self.tmp_dir.cleanup()

    def _append(self, art, prev):
        with sqlite3.connect(str(self.db_path)) as conn:
            rec = {
                "timestamp": "2026-06-06T00:00:00Z",
                "artifact_sha256": hashlib.sha256(art.encode()).hexdigest(),
                "validator": "continuity_test",
                "result": "PASS",
                "details": {},
                "duration_ms": 5,
                "previous_hash": prev,
            }
            digest = hashlib.sha256(canonical_json(rec).encode()).hexdigest()
            conn.execute("""
                INSERT INTO verification_evidence (
                    timestamp, artifact_sha256, validator, result,
                    details, duration_ms, previous_hash, evidence_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec["timestamp"], rec["artifact_sha256"], rec["validator"],
                rec["result"], canonical_json(rec["details"]), rec["duration_ms"],
                prev, digest
            ))
            conn.commit()

    def _last_hash(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute("SELECT evidence_hash FROM verification_evidence ORDER BY id DESC LIMIT 1").fetchone()
            return row[0] if row else "GENESIS"

    def test_id_gap_rejection(self):
        create_checkpoint(self.ckpt_path, self.key_path)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE verification_evidence SET id = 99 WHERE id = 3")
            conn.commit()

        with self.assertRaises(HardeningError):
            verify_database(self.ckpt_path, self.key_path)

    def test_reordered_rows_rejection(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            row1 = conn.execute("SELECT * FROM verification_evidence WHERE id = 1").fetchone()
            row2 = conn.execute("SELECT * FROM verification_evidence WHERE id = 2").fetchone()
            
            conn.execute("UPDATE verification_evidence SET artifact_sha256 = ? WHERE id = 1", (row2[2],))
            conn.execute("UPDATE verification_evidence SET artifact_sha256 = ? WHERE id = 2", (row1[2],))
            conn.commit()

        with self.assertRaises(HardeningError):
            create_checkpoint(self.ckpt_path, self.key_path)

    def test_forged_link_rejection(self):
        create_checkpoint(self.ckpt_path, self.key_path)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE verification_evidence SET previous_hash = '0'*64 WHERE id = 3")
            conn.commit()

        with self.assertRaises(HardeningError):
            verify_database(self.ckpt_path, self.key_path)


if __name__ == "__main__":
    unittest.main()
