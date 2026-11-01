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
        self.assertTrue(all(x["reason"] == "multiple_ammunition_options" for x in result["endpoints"]))

    def test_missing_inherited_ammo_is_unresolved(self):
        vehicle = self.destroyer()
        self.write("Vehicles/ParentMG.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "ParentMG_C", "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__ParentMG_C", "Properties": {}},
        ])
        result = resolve(self.root, Path(vehicle), "26058282")
        self.assertTrue(all(x["reason"] == "ammo_reference_missing" for x in result["endpoints"]))

    def test_invalid_build_or_traversal_fails(self):
        vehicle = Path(self.aircraft())
        with self.assertRaises(ValueError):
            resolve(self.root, vehicle, "unknown")
        with self.assertRaises(ValueError):
            resolve(self.root, Path("../outside.json"), "26058282")


if __name__ == "__main__":
    unittest.main()
