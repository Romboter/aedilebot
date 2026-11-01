"""Offline regression tests for private Foxhole audit provenance; no game content."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from record_audit_run import drift, run, previous_snapshot, steam_manifest


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.stats = self.root / "stats"
        self.state = self.root / "state"
        self.output = self.root / "out"
        self.pak = self.root / "vanilla.pak"
        self.pak.write_bytes(b"fixture-game-content")
        self.manifest = self.root / "steamapps" / "appmanifest_505460.acf"
        self.manifest.parent.mkdir()
        self.manifest.write_text(
            '"AppState"\n{\n    "appid" "505460"\n    "buildid" "987654"\n}\n',
            encoding="utf-8",
        )
        data = {
            "data/Damage.json": {"Blast": {"Tier1Tank": "0.2"}},
            "data/Targets.json": {"Tank": {"Health": "500"}},
            "data/Weapons.json": {"Shell": {"Damage": "100"}},
            "data/Bunker_piece.json": {"piece": {"health": [1, 2, 3]}},
            "data_manual/weapon_multipliers.json": {"Test": "manual"},
            "data_manual/target_devname_review_proposals.json": {"proposals": {}},
        }
        for name, contents in data.items():
            dump(self.source / name, contents)
        self.table_root = self.stats / "War/Content/Blueprints/Data"
        for i in range(45):
            dump(self.table_root / f"Test{i:02d}.json", [{"Rows": {"Item": {"Damage": i}}}])
        self.audit = self.root / "audit.json"
        self.audit_data = {
            "source_table_counts": {"DTDamageProfiles": 20},
            "requires_human_review": True,
            "sections": {
                "damage_mitigation": {
                    "matched": 1, "mismatched": 1, "unmapped": 1,
                    "not_compared": 0,
                    "details": [
                        {"name": "Blast", "field": "Tank", "status": "mismatched",
                         "sheet": "0.2", "game": "0.1"},
                        {"name": "TankZombie", "status": "unmapped"},
                    ],
                },
                "bunker_tiers": {
                    "matched": 0, "mismatched": 0, "unmapped": 0,
                    "not_compared": 1,
                    "details": [{"name": "core", "status": "not_compared"}],
                },
            },
        }
        dump(self.audit, self.audit_data)

    def args(self, key: str):
        return SimpleNamespace(
            pak=self.pak, stats=self.stats, audit=self.audit,
            source=self.source, appmanifest=self.manifest,
            source_sha="a" * 40, cue4parse_sha="b" * 40,
            workflow_sha="c" * 40, state=self.state,
            output=self.output, run_key=key,
        )

    def test_baseline_then_unchanged_then_table_drift(self):
        first = run(self.args("100-1"))
        self.assertEqual(first["status"], "baseline_created")
        self.assertEqual(previous_snapshot(self.state)["steam"]["build_id"], "987654")
        second = run(self.args("101-1"))
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(second["previous_run_key"], "100-1")
        dump(self.table_root / "Test10.json", [{"Rows": {"Item": {"Damage": 999}}}])
        third = run(self.args("102-1"))
        self.assertEqual(third["status"], "changed_review_required")
        self.assertEqual(third["table_changes"], ["Test10.json"])
        self.assertFalse(third["archive_changed"])
        self.assertEqual(previous_snapshot(self.state)["run_key"], "102-1")

    def test_archive_and_findings_drift(self):
        run(self.args("200-1"))
        self.pak.write_bytes(b"updated-game-content")
        self.audit_data["sections"]["damage_mitigation"]["details"][0]["game"] = "0.3"
        dump(self.audit, self.audit_data)
        outcome = run(self.args("201-1"))
        self.assertTrue(outcome["archive_changed"])
        self.assertEqual(outcome["finding_changes_total"], 1)
        self.assertEqual(outcome["status"], "changed_review_required")

    def test_missing_build_id_is_explicit(self):
        self.assertEqual(steam_manifest(None)["status"], "not_provided")
        self.manifest.write_text('"AppState" { "appid" "505460" }', encoding="utf-8")
        self.assertIsNone(steam_manifest(self.manifest)["build_id"])

    def test_corrupt_history_fails_closed(self):
        run(self.args("300-1"))
        latest = self.state / "latest.json"
        latest.write_text('{"run_key":"999-1","sha256":"fake"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            run(self.args("301-1"))

    def test_bad_audit_counts_rejected_without_state_update(self):
        self.audit_data["sections"]["damage_mitigation"]["mismatched"] = 2
        dump(self.audit, self.audit_data)
        with self.assertRaisesRegex(ValueError, "counts do not reconcile"):
            run(self.args("400-1"))
        self.assertFalse((self.state / "latest.json").exists())

    def test_same_run_key_never_reused(self):
        run(self.args("500-1"))
        with self.assertRaises(FileExistsError):
            run(self.args("500-1"))

    def test_modified_bot_input_detected(self):
        run(self.args("600-1"))
        dump(self.source / "data/Weapons.json", {"Shell": {"Damage": "123"}})
        diff = run(self.args("601-1"))
        self.assertEqual(diff["input_changes"], ["data/Weapons.json"])

    def test_bad_permissions_rejected(self):
        self.state.mkdir(mode=0o777)
        self.state.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "group/others"):
            run(self.args("700-1"))


if __name__ == "__main__":
    unittest.main()
