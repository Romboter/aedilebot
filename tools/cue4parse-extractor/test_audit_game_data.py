"""Offline unit tests for the read-only game data audit (no licensed PAK required)."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from audit_game_data import audit, markdown_report


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class GameDataAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stats = self.root / "stats"
        self.data = self.root / "data"
        self.overlay = self.root / "manual" / "weapon_multipliers.json"
        d = self.stats / "War/Content/Blueprints/Data"
        values = {
            "DTDamageProfiles": {"Blast": {"Tier1Tank": 0.5, "Trench": 0.25, "Ice": 0.9}},
            "BPAmmoDynamicData": {
                "Shell": {"Damage": 100.0, "DamageType": {"ObjectName": "EDamageType'Explosive'"}},
                "KineticRound": {"Damage": 80.0, "DamageType": {"ObjectName": "EDamageType'HeavyKinetic'"}},
            },
            "BPVehicleDynamicData": {"VehicleA": {"MaxHealth": 500}},
            "BPStructureDynamicData": {"BridgeA": {"MaxHealth": 1000}},
        }
        for name, rows in values.items():
            write_json(d / (name + ".json"), [{"Rows": rows}])
        write_json(self.data / "Damage.json", {"Blast": {"Name": "Blast", "Tier1Tank": "0.5", "Trench": "0.20"}})
        write_json(self.data / "Targets.json", {
            "A Vehicle": {"ObjectType": "Vehicles", "Dev Name": "VehicleA", "Health": "500"},
            "A Bridge": {"ObjectType": "Structures", "Dev Name": "BridgeA", "Health": "950"},
            "A Tripod": {"ObjectType": "Tripods", "Dev Name": "", "Health": "30"},
        })
        write_json(self.data / "Weapons.json", {
            "Shell": {"Dev Name": "Shell", "Damage": "100", "DamageType": "Explosive"},
            "Kinetic": {"Dev Name": "KineticRound", "Damage": "100", "DamageType": "HeavyKinetic"},
            "Variant": {"Dev Name": "Shell", "Damage": "120", "DamageType": "Explosive"},
            "Unavailable": {"Dev Name": "Unknown", "Damage": "12", "DamageType": "Explosive"},
        })
        write_json(self.data / "Bunker_piece.json", {"core": {"health": ["1", "2", "3"]}})
        write_json(self.overlay, {"Variant": "Weapon:Unrelated"})

    def test_counts_and_manual_separation(self):
        result = audit(self.stats, self.data, self.overlay)
        d = result["sections"]["damage_mitigation"]
        self.assertEqual((d["matched"], d["mismatched"]), (1, 1))
        self.assertEqual(d["source_only_fields"], ["Ice"])
        self.assertEqual(result["sections"]["vehicles_health"]["matched"], 1)
        self.assertEqual(result["sections"]["structures_health"]["mismatched"], 1)
        self.assertEqual(result["unsupported_target_categories"]["Tripods"], 1)
        w = result["sections"]["weapons_direct"]
        self.assertEqual((w["matched"], w["not_compared"], w["unmapped"], w["mismatched"]), (2, 1, 1, 0))
        self.assertEqual(result["sections"]["bunker_tiers"]["not_compared"], 1)
        self.assertTrue(result["requires_human_review"])
        self.assertIn("No bot files were changed", markdown_report(result))

    def test_comparator_is_read_only(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*.json")}
        audit(self.stats, self.data, self.overlay)
        after = {p: p.read_bytes() for p in self.root.rglob("*.json")}
        self.assertEqual(before, after)

    def test_bad_export_fails_closed(self):
        path = self.stats / "War/Content/Blueprints/Data/DTDamageProfiles.json"
        write_json(path, [{"Rows": {}}])
        with self.assertRaisesRegex(ValueError, "empty Rows"):
            audit(self.stats, self.data, self.overlay)


if __name__ == "__main__":
    unittest.main()
