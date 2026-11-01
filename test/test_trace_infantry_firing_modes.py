"""Synthetic, non-proprietary tests for separate infantry firing-mode references."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.trace_infantry_firing_modes import trace_firing_modes


class FiringModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write("Data/BPWeaponDynamicData.json", [{"Rows": {
            "RifleHeavyW": {"DamageMultiplier": 1.3},
        }}])
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {
            "RevolverAmmo": {"Damage": 60, "DamageType": {"ObjectName": "BPLightKineticDamageType", "ObjectPath": "War/Content/Blueprints/DamageTypes/LightKinetic.0"}},
            "GreenAsh": {"Damage": 0, "DamageType": {"ObjectPath": "War/Content/Blueprints/DamageTypes/Gas.0"}},
            "GrenadeW": {"Damage": 200, "DamageType": {"ObjectPath": "War/Content/Blueprints/DamageTypes/Frag.0"}},
            "ATLaunchedGrenadeW": {"Damage": 425, "DamageType": {"ObjectPath": "War/Content/Blueprints/DamageTypes/AT.0"}},
        }}])
        self.write("ItemPickups/RiflePickup.json", [
            {"Name": "Default__RiflePickup_C", "Properties": {
                "CodeName": "RifleHeavyW",
                "ItemComponentClass": {"ObjectPath": "War/Content/Blueprints/ItemPickups/RifleComponent.0"},
            }},
        ])
        self.component({
            "CompatibleAmmoCodeName": "RevolverAmmo",
            "GrenadeMultiAmmo": {"CompatibleAmmoNames": ["GreenAsh", "GrenadeW", "ATLaunchedGrenadeW"]},
            "GrenadeClasses": [
                {"ObjectPath": f"War/Content/Blueprints/Items/Grenade{i}.0"} for i in range(3)
            ],
        })
        for i in range(3):
            self.write(f"Items/Grenade{i}.json", [
                {"Type": "BlueprintGeneratedClass", "Name": f"Grenade{i}_C",
                 "SuperStruct": {"ObjectPath": "/Script/War"}},
                {"Name": f"Default__Grenade{i}_C", "Properties": {}},
            ])

    def write(self, relative, obj):
        path = self.root / relative
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(json.dumps(obj), encoding="utf-8")

    def component(self, props):
        self.write("ItemPickups/RifleComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "RifleComponent_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__RifleComponent_C", "Properties": props},
        ])

    def run_resolver(self):
        return trace_firing_modes(self.root, Path("ItemPickups/RiflePickup.json"), "26058282")

    def test_primary_cartridge_is_separate_from_grenade_mode(self):
        report = self.run_resolver()
        primary = report["primary_fire"]
        self.assertEqual(primary["ammo_code_name"], "RevolverAmmo")
        self.assertAlmostEqual(primary["derived_direct_damage"], 97.5)
        mode = report["secondary_modes"][0]
        self.assertEqual(mode["mode"], "rifle_grenade_attachment")
        self.assertEqual([x["ammo"] for x in mode["ammo_variants"]],
                         ["GreenAsh", "GrenadeW", "ATLaunchedGrenadeW"])
        self.assertEqual([x["raw_ammo_damage"] for x in mode["ammo_variants"]],
                         [0, 200, 425])
        self.assertEqual(len(mode["projectile_classes"]), 3)
        self.assertFalse(mode["ammo_to_projectile_associations_verified"])
        self.assertIsNone(mode["damage_multiplier_source"])
        self.assertNotIn("derived_direct_damage", mode)
        self.assertFalse(report["safe_for_unattended_publication"])

    def test_equal_array_lengths_do_not_create_positional_links(self):
        mode = self.run_resolver()["secondary_modes"][0]
        self.assertEqual(len(mode["projectile_classes"]), len(mode["ammo_variants"]))
        self.assertEqual(mode["reason"], "ammo_to_projectile_and_multiplier_relationship_unverified")

    def test_missing_grenade_ammo_row_remains_unresolved(self):
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {
            "RevolverAmmo": {"Damage": 60, "DamageType": {"ObjectName": "BPLightKineticDamageType"}},
            "GreenAsh": {"Damage": 0, "DamageType": {"ObjectPath": "War/Content/Blueprints/DamageTypes/Gas.0"}},
            "GrenadeW": {"Damage": 200, "DamageType": {"ObjectPath": "War/Content/Blueprints/DamageTypes/Frag.0"}},
        }}])
        mode = self.run_resolver()["secondary_modes"][0]
        self.assertEqual(mode["reason"], "one_or_more_ammo_rows_unresolved")
        self.assertEqual(mode["ammo_variants"][-1]["status"], "named_ammo_row_missing")

    def test_duplicate_grenade_ammo_options_fail_closed(self):
        self.component({
            "CompatibleAmmoCodeName": "RevolverAmmo",
            "GrenadeMultiAmmo": {"CompatibleAmmoNames": ["GreenAsh", "GreenAsh"]},
        })
        mode = self.run_resolver()["secondary_modes"][0]
        self.assertEqual(mode["reason"], "invalid_or_missing_explicit_ammo_options")

    def test_missing_projectile_export_preserves_explicit_reference(self):
        (self.root / "Items/Grenade1.json").unlink()
        mode = self.run_resolver()["secondary_modes"][0]
        self.assertEqual(mode["reason"], "projectile_class_exports_missing")
        self.assertEqual(mode["projectile_classes"][1]["exported"], False)

    def test_inherited_secondary_mode_tracks_parent_source(self):
        self.write("ItemPickups/BaseRifleComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "BaseRifleComponent_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__BaseRifleComponent_C", "Properties": {
                "GrenadeMultiAmmo": {"CompatibleAmmoNames": ["GrenadeW"]},
                "GrenadeClasses": [{"ObjectPath": "War/Content/Blueprints/Items/Grenade0.0"}],
            }},
        ])
        self.write("ItemPickups/RifleComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "RifleComponent_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/ItemPickups/BaseRifleComponent.1"}},
            {"Name": "Default__RifleComponent_C", "Properties": {"CompatibleAmmoCodeName": "RevolverAmmo"}},
        ])
        mode = self.run_resolver()["secondary_modes"][0]
        self.assertEqual(mode["ammo_variants"][0]["ammo"], "GrenadeW")
        self.assertEqual(mode["ammo_evidence"]["asset"], "ItemPickups/BaseRifleComponent.json")

    def test_non_grenade_component_stays_primary_only(self):
        self.component({"CompatibleAmmoCodeName": "RevolverAmmo"})
        report = self.run_resolver()
        self.assertEqual(report["secondary_modes"], [])
        self.assertEqual(report["primary_fire"]["ammo_code_name"], "RevolverAmmo")


if __name__ == "__main__":
    unittest.main()
