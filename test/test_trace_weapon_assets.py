"""Offline tests of weapon asset reference discovery (no game assets distributed)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import trace_weapon_assets as t


class TraceWeaponAssetsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "blueprints"
        self.root.mkdir()
        self.data = self.root / "Data"
        self.data.mkdir()
        self.export = [
            {
                "Type": "BlueprintGeneratedClass",
                "Name": "BPShipMG_C",
                "Properties": {
                    "SupportedAmmoTypes": [{"ObjectName": "AmmoClass'/Game/War/MGAmmo.MGAmmo_C'"}],
                    "MountedWeapon": {"ObjectPath": "War/Content/Blueprints/Weapons/BPShipMG.BPShipMG_C"},
                    "MountComponent": {"ObjectName": "BPMount'AircraftScoutW_HMG'"},
                    "DamageMultiplier": 1.2,
                    "DisplayName": "MGAmmo (display text only)",
                },
            },
            {
                "Name": "OtherShip",
                "Properties": {
                    "AmmoClass": {"ObjectName": "AmmoClass'OtherAmmo'"},
                    "MountClass": {"ObjectName": "BPMount'OtherMount'"},
                    "DamageMultiplier": 1.2,
                },
            },
        ]
        self.save()

    def save(self):
        (self.root / "BPShipMG.json").write_text(json.dumps(self.export), encoding="utf-8")

    def test_references_are_record_level_and_have_json_paths(self):
        report = t.scan(self.root, {"ammo": "MGAmmo", "mount": "AircraftScoutW_HMG"})
        self.assertEqual(report["scanned_files"], 1)
        self.assertEqual(len(report["matches"]), 1)
        first = report["matches"][0]
        self.assertIn("BPShipMG_C", first["record"])
        self.assertEqual(first["roles_present"], ["ammo", "mount"])
        props = [x["property"] for x in first["references"]]
        self.assertIn("Properties/SupportedAmmoTypes/0/ObjectName", props)
        self.assertIn("Properties/MountComponent/ObjectName", props)
        self.assertIn("not_verified", report["status"])

    def test_numerically_equal_damage_multipliers_are_not_edges(self):
        self.export[0]["Properties"].pop("SupportedAmmoTypes")
        self.export[0]["Properties"].pop("MountComponent")
        self.save()
        report = t.scan(self.root, {"ammo": "MGAmmo", "mount": "AircraftScoutW_HMG"})
        self.assertEqual(report["matches"], [])

    def test_display_names_are_not_asset_references(self):
        self.export[0]["Properties"].pop("SupportedAmmoTypes")
        self.export[0]["Properties"].pop("MountComponent")
        self.export[0]["Properties"]["DisplayName"] = "MGAmmo"
        self.save()
        self.assertEqual(t.scan(self.root, {"ammo": "MGAmmo"})["matches"], [])

    def test_identifier_not_substring_of_a_longer_token(self):
        self.export[0]["Properties"]["SupportedAmmoTypes"][0]["ObjectName"] = "BPAmmo'MGAmmoOld'"
        self.save()
        report = t.scan(self.root, {"ammo": "MGAmmo"})
        self.assertEqual(report["matches"], [])

    def test_table_rows_are_separate_records(self):
        self.export.clear()
        self.save()
        (self.data / "BPWeaponDynamicData.json").write_text(json.dumps([
            {"Rows": {
                "ShipGun": {"AmmoClass": {"ObjectName": "BPAmmo'MGAmmo'"}},
                "OtherGun": {"AmmoClass": {"ObjectName": "BPAmmo'OtherAmmo'"}},
            }}
        ]), encoding="utf-8")
        report = t.scan(self.root, {"ammo": "MGAmmo"})
        self.assertEqual(len(report["matches"]), 1)
        self.assertIn("Rows/ShipGun", report["matches"][0]["record"])

    def test_row_name_itself_is_not_a_reference(self):
        self.export.clear()
        self.save()
        (self.data / "BPAmmoDynamicData.json").write_text(
            json.dumps([{"Rows": {"MGAmmo": {"Damage": 55, "DamageType": {"ObjectName": "Damage'HeavyKinetic'"}}}}]),
            encoding="utf-8",
        )
        self.assertFalse(t.scan(self.root, {"ammo": "MGAmmo"})["matches"])

    def test_invalid_json_is_reported_not_silently_accepted(self):
        (self.root / "bad.json").write_text("{bad", encoding="utf-8")
        report = t.scan(self.root, {"ammo": "MGAmmo"})
        self.assertEqual(len(report["invalid_json_files"]), 1)
        self.assertEqual(report["scanned_files"], 2)

    def test_file_limit_rejects_unbounded_crawl(self):
        with self.assertRaisesRegex(ValueError, "max-files"):
            t.scan(self.root, {"ammo": "MGAmmo"}, max_files=0)

    def test_choose_existing_sheet_ids_not_multiplier_overlay_proxy(self):
        sheet = {
            "Ship 12.7mm (+20% HV)": {
                "Dev Name": "MGAmmo",
                "Additional Names": "Ship MG",
                "Damage": "82.5",
            },
            "Scout 20mm": {
                "Dev Name": "AircraftAmmo", "Vehicle Dev Name": "AircraftScoutW",
                "Mount Dev Name": "AircraftScoutW_HMG",
                "Damage": "53.625",
            },
        }
        sheet_path = self.root / "Weapons.json"
        sheet_path.write_text(json.dumps(sheet), encoding="utf-8")
        ids, meta = t.selected_identifiers(
            "Ship 12.7mm (+20% HV)", sheet_path, None, None, None,
        )
        self.assertEqual(ids, {"ammo": "MGAmmo"})
        self.assertEqual(meta["weapon_name"], "Ship 12.7mm (+20% HV)")
        scout, _ = t.selected_identifiers("Scout 20mm", sheet_path, None, None, None)
        self.assertEqual(scout, {
            "ammo": "AircraftAmmo", "mount": "AircraftScoutW_HMG",
            "vehicle": "AircraftScoutW",
        })

    def test_missing_query_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Supply"):
            t.selected_identifiers(None, None, None, None, None)
        with self.assertRaisesRegex(ValueError, "requires"):
            t.selected_identifiers("Ship 12.7mm", None, None, None, None)


if __name__ == "__main__":
    unittest.main()
