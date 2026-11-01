"""Hermetic tests for typed Blueprint weapon endpoint resolution."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.resolve_blueprint_weapons import resolve


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "Blueprints"
        self.root.mkdir()
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {
            "AircraftAmmo": {"Damage": 65, "DamageType": {"ObjectName": "Shrapnel"}},
            "ATRifleAmmo": {"Damage": 150, "DamageType": {"ObjectName": "AntiTankKinetic"}},
            "MGAmmo": {"Damage": 55, "DamageType": {"ObjectName": "HeavyKinetic"}},
        }}])
        self.write("Data/BPMountDynamicData.json", [{"Rows": {
            "AircraftFighterW_HMG": {"DamageMultiplier": 1.0},
            "AircraftFighterW_Cannon": {"DamageMultiplier": 1.5},
            "LargeShipDestroyerCMachineGunner": {"DamageMultiplier": 1.2},
            "UnrelatedGun": {"DamageMultiplier": 1.2},
        }}])

    def write(self, relative, payload):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload), encoding="utf-8")

    def aircraft(self):
        self.write("Vehicles/Fighter.json", [
            {"Name": "Default__Fighter_C", "Properties": {"WeaponConfigs": [
                {"AmmoCodeName": "AircraftAmmo", "WeaponCodeName": "AircraftFighterW_HMG"},
                {"AmmoCodeName": "ATRifleAmmo", "WeaponCodeName": "AircraftFighterW_Cannon"},
            ]}},
        ])
        return "Vehicles/Fighter.json"

    def destroyer(self, mount_code="LargeShipDestroyerCMachineGunner"):
        ref = "War/Content/Blueprints/Vehicles/MGComponent.0"
        self.write("Vehicles/Ship.json", [
            {"Name": "Default__Ship_C", "Properties": {}},
            {"Type": "VehicleSeatComponent", "Name": "GunnerSeat4_GEN_VARIABLE", "Properties": {
                "MountCodeName": mount_code,
                "MountComponent": {"ObjectPath": ref},
            }},
            {"Type": "VehicleSeatComponent", "Name": "GunnerSeat5_GEN_VARIABLE", "Properties": {
                "MountCodeName": mount_code,
                "MountComponent": {"ObjectPath": ref},
            }},
        ])
        self.write("Vehicles/MGComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "MGComponent_C", "SuperStruct": {
                "ObjectPath": "War/Content/Blueprints/Vehicles/ParentMG.0"}},
            {"Name": "Default__MGComponent_C", "Properties": {}},
        ])
        self.write("Vehicles/ParentMG.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "ParentMG_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__ParentMG_C", "Properties": {"AmmoName": "MGAmmo"}},
        ])
        return "Vehicles/Ship.json"

    def test_aircraft_multiple_independent_barrels(self):
        result = resolve(self.root, Path(self.aircraft()), "26058282")
        self.assertEqual([x["damage"] for x in result["endpoints"]], [81.25, 281.25])
        self.assertEqual([x["ammo"] for x in result["endpoints"]], ["AircraftAmmo", "ATRifleAmmo"])
        self.assertTrue(all(not x["safe_for_unattended_publication"] for x in result["endpoints"]))

    def test_destroyer_inherited_ammo_two_seats(self):
        result = resolve(self.root, Path(self.destroyer()), "26058282")
        self.assertEqual([x["damage"] for x in result["endpoints"]], [82.5, 82.5])
        self.assertTrue(all(any(e.get("asset") == "Vehicles/ParentMG.json" for e in x["edges"])
                            for x in result["endpoints"]))

    def test_numeric_match_does_not_supply_missing_mount(self):
        result = resolve(self.root, Path(self.destroyer("OtherGun")), "26058282")
        self.assertTrue(all(x["status"] == "unresolved" for x in result["endpoints"]))
        self.assertTrue(all(x["reason"] == "named_mount_row_missing" for x in result["endpoints"]))

    def test_changed_named_mount_does_not_borrow_unrelated_factor(self):
        self.write("Data/BPMountDynamicData.json", [{"Rows": {
            "LargeShipDestroyerCMachineGunner": {"DamageMultiplier": 1.1},
            "UnrelatedGun": {"DamageMultiplier": 1.2},
        }}])
        result = resolve(self.root, Path(self.destroyer()), "26058282")
        for endpoint in result["endpoints"]:
            self.assertAlmostEqual(endpoint["damage"], 75.625)

    def test_ambiguous_multi_ammo_fails_closed(self):
        vehicle = self.destroyer()
        self.write("Vehicles/ParentMG.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "ParentMG_C", "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__ParentMG_C", "Properties": {
                "MultiAmmo": {"CompatibleAmmoNames": ["MGAmmo", "ATRifleAmmo"]}}},
        ])
        result = resolve(self.root, Path(vehicle), "26058282")
        self.assertTrue(all(x["reason"] == "multiple_ammunition_variants_require_explicit_selection" for x in result["endpoints"]))
        self.assertTrue(all("damage" not in x for x in result["endpoints"]))

    def test_missing_inherited_ammo_is_unresolved(self):
        vehicle = self.destroyer()
        self.write("Vehicles/ParentMG.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "ParentMG_C", "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__ParentMG_C", "Properties": {}},
        ])
        result = resolve(self.root, Path(vehicle), "26058282")
        self.assertTrue(all(x["reason"] == "ammo_reference_missing" for x in result["endpoints"]))

    def test_inherited_vehicle_seat_properties_not_guessed_from_child(self):
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {"LightTankAmmo": {"Damage": 600.0, "DamageType": {"ObjectName": "Explosive"}}}}])
        self.write("Data/BPMountDynamicData.json", [{"Rows": {
            "LightTankGunnerC": {"DamageMultiplier": 1.0},
        }}])
        self.write("Vehicles/LightTank/BPLightTankBaseC.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "BaseC_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__BaseC_C", "Properties": {}},
            {"Type": "VehicleSeatComponent", "Name": "GunnerSeat1_GEN_VARIABLE",
             "Properties": {"MountCodeName": "LightTankGunnerC",
                            "MountComponent": {"ObjectPath": "War/Content/Blueprints/Vehicles/LightTank/BPLightTankGunnerMountComponentW.0"}}},
        ])
        self.write("Vehicles/LightTank/BPLightTankC.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "TankC_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Vehicles/LightTank/BPLightTankBaseC.1"}},
            {"Name": "Default__TankC_C", "Properties": {}},
            {"Type": "VehicleSeatComponent", "Name": "GunnerSeat1_GEN_VARIABLE",
             "Properties": {"Direction": "ESeatDirection::Center"}},
        ])
        self.write("Vehicles/LightTank/BPLightTankGunnerMountComponentW.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "TankGunnerW_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__TankGunnerW_C", "Properties": {
                "MultiAmmo": {"CompatibleAmmoNames": ["LightTankAmmo"]}}},
        ])
        result = resolve(self.root, Path("Vehicles/LightTank/BPLightTankC.json"), "26058282")
        self.assertEqual(len(result["endpoints"]), 1)
        endpoint = result["endpoints"][0]
        self.assertEqual(endpoint["mount"], "LightTankGunnerC")
        self.assertEqual(endpoint["ammo"], "LightTankAmmo")
        self.assertAlmostEqual(endpoint["damage"], 600.0)
        self.assertTrue(any(e.get("asset") == "Vehicles/LightTank/BPLightTankBaseC.json" for e in endpoint["edges"]))

    def test_vehicle_with_weapon_configs_and_gunner_seat_resolves_both(self):
        self.aircraft()
        self.write("Vehicles/Fighter.json", [
            {"Name": "Default__Fighter_C", "Properties": {"WeaponConfigs": [
                {"AmmoCodeName": "AircraftAmmo", "WeaponCodeName": "AircraftFighterW_HMG"}]}},
            {"Type": "VehicleSeatComponent", "Name": "GunnerSeat1_GEN_VARIABLE",
             "Properties": {"MountCodeName": "LargeShipDestroyerCMachineGunner",
                            "MountComponent": {"ObjectPath": "War/Content/Blueprints/Vehicles/MGComponent.0"}}},
        ])
        self.write("Vehicles/MGComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "MG_C", "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__MG_C", "Properties": {"AmmoName": "MGAmmo"}},
        ])
        endpoints = resolve(self.root, Path("Vehicles/Fighter.json"), "26058282")["endpoints"]
        self.assertEqual(len(endpoints), 2)
        self.assertEqual({x["endpoint"] for x in endpoints}, {"WeaponConfigs/0", "GunnerSeat1_GEN_VARIABLE"})

    def test_incomplete_seat_reference_is_unresolved_not_dropped(self):
        self.write("Vehicles/Ship.json", [
            {"Name": "Default__Ship_C", "Properties": {}},
            {"Type": "VehicleSeatComponent", "Name": "GunnerSeat1_GEN_VARIABLE", "Properties": {
                "MountCodeName": "LargeShipDestroyerCMachineGunner",
            }},
        ])
        result = resolve(self.root, Path("Vehicles/Ship.json"), "26058282")
        self.assertEqual(len(result["endpoints"]), 1)
        self.assertEqual(result["endpoints"][0]["status"], "unresolved")
        self.assertEqual(result["endpoints"][0]["reason"], "mount_component_reference_missing")

    def test_inherited_weapon_configs_cite_parent_source(self):
        self.write("Vehicles/FighterBase.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "FighterBase_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__FighterBase_C", "Properties": {"WeaponConfigs": [
                {"AmmoCodeName": "AircraftAmmo", "WeaponCodeName": "AircraftFighterW_HMG"},
            ]}},
        ])
        self.write("Vehicles/Fighter.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Fighter_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Vehicles/FighterBase.1"}},
            {"Name": "Default__Fighter_C", "Properties": {"OtherProperty": 42}},
        ])
        result = resolve(self.root, Path("Vehicles/Fighter.json"), "26058282")
        self.assertEqual(len(result["endpoints"]), 1)
        self.assertTrue(all(e["asset"] == "Vehicles/FighterBase.json"
                            for e in result["endpoints"][0]["edges"]))

    def test_multi_ammo_variants_list_real_rows_without_default(self):
        vehicle = self.destroyer()
        self.write("Vehicles/ParentMG.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "ParentMG_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__ParentMG_C", "Properties": {
                "MultiAmmo": {"CompatibleAmmoNames": ["MGAmmo", "ATRifleAmmo"]}}},
        ])
        result = resolve(self.root, Path(vehicle), "26058282")
        for endpoint in result["endpoints"]:
            self.assertEqual(endpoint["status"], "unresolved")
            self.assertEqual(endpoint["reason"], "multiple_ammunition_variants_require_explicit_selection")
            self.assertNotIn("damage", endpoint)
            self.assertEqual([x["ammo"] for x in endpoint["variant_candidates"]], ["MGAmmo", "ATRifleAmmo"])
            self.assertEqual([round(x["damage"], 5) for x in endpoint["variant_candidates"]], [82.5, 225.0])
            self.assertTrue(all(x["source_rows"] for x in endpoint["variant_candidates"]))

    def test_zero_damage_flare_is_known_not_missing(self):
        vehicle = self.destroyer()
        self.write("Vehicles/ParentMG.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "ParentMG_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__ParentMG_C", "Properties": {
                "MultiAmmo": {"CompatibleAmmoNames": ["MGAmmo", "FlareAmmo"]}}},
        ])
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {
            "MGAmmo": {"Damage": 55, "DamageType": {"ObjectName": "HeavyKinetic"}},
            "FlareAmmo": {"Damage": 0, "DamageType": {"ObjectName": "Flare"}},
        }}])
        result = resolve(self.root, Path(vehicle), "26058282")
        for endpoint in result["endpoints"]:
            self.assertEqual(endpoint["status"], "unresolved")
            self.assertEqual(endpoint["variant_candidates"][1]["status"], "non_direct_damage_ammunition")
            self.assertEqual(endpoint["variant_candidates"][1]["damage"], 0)

    def test_missing_variant_row_fails_closed_without_borrowing_another(self):
        vehicle = self.destroyer()
        self.write("Vehicles/ParentMG.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "ParentMG_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__ParentMG_C", "Properties": {
                "MultiAmmo": {"CompatibleAmmoNames": ["MGAmmo", "MissingAmmo"]}}},
        ])
        result = resolve(self.root, Path(vehicle), "26058282")
        for endpoint in result["endpoints"]:
            self.assertEqual(endpoint["reason"], "one_or_more_ammunition_variants_unresolved")
            self.assertEqual(endpoint["variant_candidates"][1]["reason"], "named_ammo_row_missing")

    def test_duplicate_variant_options_fail_closed(self):
        vehicle = self.destroyer()
        self.write("Vehicles/ParentMG.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "ParentMG_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__ParentMG_C", "Properties": {
                "MultiAmmo": {"CompatibleAmmoNames": ["MGAmmo", "MGAmmo"]}}},
        ])
        result = resolve(self.root, Path(vehicle), "26058282")
        self.assertTrue(all(e["reason"] == "invalid_or_duplicate_ammunition_options"
                            for e in result["endpoints"]))

    def test_invalid_build_or_traversal_fails(self):
        vehicle = Path(self.aircraft())
        with self.assertRaises(ValueError):
            resolve(self.root, vehicle, "unknown")
        with self.assertRaises(ValueError):
            resolve(self.root, Path("../outside.json"), "26058282")


if __name__ == "__main__":
    unittest.main()
