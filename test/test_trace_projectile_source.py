"""Offline checks for explicit projectile and explosion reference edges."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.trace_projectile_source import trace


class ProjectileTraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {
            "ATRPGAmmo": {"Damage": 550},
        }}])
        self.put("Vehicles/Mech/BPGunner.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "BPGunner_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__BPGunner_C", "Properties": {
                "AmmoName": "RPGAmmo",
                "ProjectileClass": {"ObjectPath": "War/Content/Blueprints/Items/RocketProjectile.1"},
            }},
        ])
        self.put("Items/RocketProjectile.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "RocketProjectile_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__RocketProjectile_C", "Properties": {
                "ExplosiveCodeName": "RpgAmmo",
                "ExplosionTemplate": {"ObjectPath": "War/Content/Blueprints/Items/RPGExplosion.1"},
            }},
        ])
        self.put("Items/RPGExplosion.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "RPGExplosion_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__RPGExplosion_C", "Properties": {
                "ExplosionSound": {"ObjectPath": "War/Content/Audio/RPGSound.0"},
            }},
        ])

    def put(self, name, obj):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj), encoding="utf-8")

    def run_trace(self):
        return trace(self.root, Path("Vehicles/Mech/BPGunner.json"), "26058282")

    def test_projectile_chain_traced_but_not_a_numeric_ammo_alias(self):
        out = self.run_trace()
        self.assertEqual(out["declared_ammo_name"], "RPGAmmo")
        self.assertEqual(out["projectile_package"], "Items/RocketProjectile")
        self.assertEqual(out["projectile_explosive_code"], "RpgAmmo")
        self.assertEqual(out["ammunition_code_spelling"], "case_only_difference")
        self.assertEqual(out["explosion_template_package"], "Items/RPGExplosion")
        self.assertFalse(out["ammo_table_evidence"]["exact_row_present"])
        self.assertIn("declared_ammo_name_missing_from_dynamic_data", out["gaps"])
        self.assertFalse(out["safe_for_unattended_publication"])
        self.assertNotIn("damage", out)

    def test_missing_projectile_export_fails_closed(self):
        (self.root / "Items/RocketProjectile.json").unlink()
        out = self.run_trace()
        self.assertEqual(out["gaps"], ["referenced_projectile_package_not_exported"])
        self.assertNotIn("ammo_table_evidence", out)

    def test_unrelated_equal_damage_is_not_substituted(self):
        out = self.run_trace()
        self.assertFalse(out["ammo_table_evidence"]["exact_row_present"])
        self.assertNotIn("Damage", out)
        self.assertNotIn("damage", out)

    def test_native_projectile_reference_unresolved(self):
        self.put("Vehicles/Mech/BPGunner.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "BPGunner_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__BPGunner_C", "Properties": {
                "AmmoName": "RPGAmmo",
                "ProjectileClass": {"ObjectPath": "/Script/War"},
            }},
        ])
        out = self.run_trace()
        self.assertEqual(out["gaps"], ["explicit_projectile_class_not_exported"])


if __name__ == "__main__":
    unittest.main()
