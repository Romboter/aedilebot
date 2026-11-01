#!/usr/bin/env python3
"""Synthetic fail-closed tests for derived audit-history backup verifier."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from backup_audit_history import backup, verify


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "snapshot"
        self.runs = self.state / "runs"
        self.runs.mkdir(parents=True, mode=0o700)
        os.chmod(self.state, 0o700)
        doc = {"schema_version": 1, "run_key": "123-1"}
        data = (json.dumps(doc) + "\n").encode()
        (self.runs / "123-1.json").write_bytes(data)
        (self.state / "latest.json").write_text(json.dumps({
            "run_key": "123-1", "sha256": hashlib.sha256(data).hexdigest()
        }))
        self.manifest = {"schema_version": 1, "files": {
            "latest.json": hashlib.sha256((self.state / "latest.json").read_bytes()).hexdigest(),
            "runs/123-1.json": hashlib.sha256(data).hexdigest(),
        }}
        (self.state / "manifest.json").write_text(json.dumps(self.manifest))
        for path in self.state.rglob("*.json"):
            os.chmod(path, 0o600)

    def test_valid_inventory(self):
        self.assertEqual(verify(self.state), 2)

    def test_corrupt_snapshot_fails(self):
        (self.runs / "123-1.json").write_text('{"tampered":true}')
        with self.assertRaises(ValueError):
            verify(self.state)

    def test_missing_snapshot_fails(self):
        (self.runs / "123-1.json").unlink()
        with self.assertRaises(ValueError):
            verify(self.state)

    def test_symlink_fails(self):
        (self.runs / "123-1.json").unlink()
        (self.runs / "123-1.json").symlink_to(self.state / "latest.json")
        with self.assertRaises(ValueError):
            verify(self.state)

    def test_same_filesystem_rejected(self):
        destination = self.root / "destination"
        destination.mkdir(mode=0o700)
        with self.assertRaisesRegex(ValueError, "same filesystem"):
            backup(self.state, destination, "test01")


if __name__ == "__main__":
    unittest.main()
