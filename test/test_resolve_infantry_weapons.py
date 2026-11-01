"""Synthetic tests for pickup → component → ammo → dynamic-row identities."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.resolve_infantry_weapons import resolve_infantry


class InfantryResolverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write("Data/BPWeaponDynamicData.json", [{"Rows": {
            "RifleLightW": {"DamageMultiplier": 0.888},
            "UnrelatedWeapon": {"DamageMultiplier": 0.888},
        }}])
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {
            "RifleAmmo": {"Damage": 45.0, "DamageType": {"ObjectName": "BPLightKineticDamageType_C"}},
        }}])
        self.write("ItemPickups/BlakerowPickup.json", [
            {"Name": "Default__BlakerowPickup_C", "Properties": {
                "CodeName": "RifleLightW",
                "ItemComponentClass": {"ObjectPath": "War/Content/Blueprints/Items/BPCarbineComponent.0"}}},
        ])
        self.write("Items/BPCarbineComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "BPCarbineComponent_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__BPCarbineComponent_C", "Properties": {
                "CompatibleAmmoCodeName": "RifleAmmo"}},
        ])

    def write(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data), encoding="utf-8")

    def test_component_name_can_differ_from_pickup_identity(self):
        result = resolve_infantry(self.root, Path("ItemPickups/BlakerowPickup.json"), "26058282")
        self.assertEqual(result["weapon_code_name"], "RifleLightW")
        self.assertEqual(result["ammo_code_name"], "RifleAmmo")
        self.assertAlmostEqual(result["derived_direct_damage"], 49.95)
        self.assertFalse(result["safe_for_unattended_publication"])
        self.assertTrue(any(e.get("asset") == "Items/BPCarbineComponent.json" for e in result["evidence"]))

    def test_equal_multiplier_unrelated_weapon_does_not_match(self):
        self.write("Data/BPWeaponDynamicData.json", [{"Rows": {
            "UnrelatedWeapon": {"DamageMultiplier": 0.888},
        }}])
        result = resolve_infantry(self.root, Path("ItemPickups/BlakerowPickup.json"), "26058282")
        self.assertEqual(result["status"], "unresolved")
        self.assertEqual(result["reason"], "named_weapon_or_ammo_row_absent")

    def test_component_inheritance_can_provide_ammo(self):
        self.write("Items/BPCarbineComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "BPCarbineComponent_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Items/ParentCarbine.0"}},
            {"Name": "Default__BPCarbineComponent_C", "Properties": {}},
        ])
        self.write("Items/ParentCarbine.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "ParentCarbine_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__ParentCarbine_C", "Properties": {"CompatibleAmmoCodeName": "RifleAmmo"}},
        ])
        result = resolve_infantry(self.root, Path("ItemPickups/BlakerowPickup.json"), "26058282")
        self.assertEqual(result["ammo_code_name"], "RifleAmmo")
        self.assertTrue(any(e.get("asset") == "Items/ParentCarbine.json" for e in result["evidence"]))

    def test_missing_component_fails_closed(self):
        self.write("ItemPickups/BlakerowPickup.json", [
            {"Name": "Default__BlakerowPickup_C", "Properties": {
                "CodeName": "RifleLightW",
                "ItemComponentClass": {"ObjectPath": "War/Content/Blueprints/Items/Missing.0"}}},
        ])
        result = resolve_infantry(self.root, Path("ItemPickups/BlakerowPickup.json"), "26058282")
        self.assertEqual(result["reason"], "component_reference_unresolved")

    def test_no_ammo_reference_fails_closed(self):
        self.write("Items/BPCarbineComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "BPCarbineComponent_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__BPCarbineComponent_C", "Properties": {}},
        ])
        result = resolve_infantry(self.root, Path("ItemPickups/BlakerowPickup.json"), "26058282")
        self.assertEqual(result["reason"], "component_compatible_ammo_not_found_in_exported_defaults")


if __name__ == "__main__":
    unittest.main()
