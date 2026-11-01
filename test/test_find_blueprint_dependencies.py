"""Offline tests for exact Blueprint dependency discovery."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.find_blueprint_dependencies import asset_path, discover


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.save("Vehicles/Child.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Child_C", "SuperStruct": {
                "ObjectPath": "War/Content/Blueprints/Vehicles/Parent.1"}},
            {"Type": "VehicleSeatComponent", "Name": "GunnerSeat1_GEN_VARIABLE", "Properties": {
                "MountComponent": {"ObjectPath": "War/Content/Blueprints/Vehicles/GunnerComponent.0"}}},
            {"Name": "Default__Child_C", "Properties": {
                "ItemComponentClass": {"ObjectPath": "War/Content/Blueprints/Items/AmmoComponent.0"},
                "DisplayName": "Not a Blueprint edge"}},
        ])

    def save(self, name, objects):
        f = self.root / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(objects), encoding="utf-8")

    def test_discovers_only_explicit_missing_packages(self):
        inv = discover(self.root)
        self.assertEqual(inv["scanned_packages"], 1)
        self.assertEqual(inv["explicit_edges"], 3)
        self.assertEqual([x["package"] for x in inv["missing_packages"]],
                         ["Items/AmmoComponent", "Vehicles/GunnerComponent", "Vehicles/Parent"])

    def test_present_parent_removed_from_missing_list(self):
        self.save("Vehicles/Parent.json", [])
        self.assertEqual(discover(self.root)["referenced_packages"], 3)
        self.assertEqual(len(discover(self.root)["missing_packages"]), 2)

    def test_native_references_ignored(self):
        self.save("Vehicles/Parent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Parent_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}}])
        self.assertEqual(len(discover(self.root)["missing_packages"]), 2)

    def test_invalid_paths_fail_closed(self):
        for value in [
            "War/Content/Blueprints/../Outside.0",
            "War/Content/Blueprints/Vehicles/../../Outside.0",
            "War/Content/Blueprints/Vehicles/Bad;name.0",
        ]:
            with self.assertRaises(ValueError):
                asset_path(value)
        self.assertIsNone(asset_path("/Script/War"))

    def test_explicit_projectile_and_grenade_references_are_dependencies(self):
        self.save("Items/RifleComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Rifle_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Rifle_C", "Properties": {
                "ProjectileClass": {"ObjectPath": "War/Content/Blueprints/Items/RPGProjectile.1"},
                "ProjectileClasses": [{"ObjectPath": "War/Content/Blueprints/Items/RPGVariant.1"}],
                "GrenadeClasses": [
                    {"ObjectPath": "War/Content/Blueprints/Items/GrenadeA.0"},
                    {"ObjectPath": "War/Content/Blueprints/Items/GrenadeB.0"},
                ],
                "ExplosionTemplate": {"ObjectPath": "War/Content/Blueprints/Items/Explosion.1"},
            }},
        ])
        from scripts.find_blueprint_dependencies import direct_edges
        edges = list(direct_edges(self.root, self.root / "Items/RifleComponent.json"))
        self.assertEqual([e["field"] for e in edges],
            ["ProjectileClass", "ExplosionTemplate", "ProjectileClasses[0]",
             "GrenadeClasses[0]", "GrenadeClasses[1]"])
        self.assertEqual(edges[0]["package"], "Items/RPGProjectile")
        self.assertEqual(edges[2]["object_path"], "War/Content/Blueprints/Items/RPGVariant.1")
        inv = discover(self.root)
        self.assertEqual(inv["explicit_edges"], 8)
        self.assertEqual(len(inv["missing_packages"]), 8)

    def test_malformed_class_list_fails_closed(self):
        self.save("Items/RifleComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Rifle_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Rifle_C", "Properties": {"GrenadeClasses": "invalid"}},
        ])
        with self.assertRaisesRegex(ValueError, "Malformed GrenadeClasses"):
            discover(self.root)

    def test_reports_missing_reference_with_source_hash_and_field(self):
        report = discover(self.root)
        self.assertEqual(report["resolved_edge_references"], 0)
        self.assertEqual(report["unresolved_edge_references"], 3)
        self.assertEqual(report["edge_type_counts"]["SuperStruct"], 1)
        edge = next(x for x in report["missing_source_edges"] if x["field"] == "SuperStruct")
        self.assertEqual(edge["source_asset"], "Vehicles/Child.json")
        self.assertEqual(edge["package"], "Vehicles/Parent")
        self.assertEqual(edge["object_path"], "War/Content/Blueprints/Vehicles/Parent.1")
        self.assertEqual(len(edge["source_sha256"]), 64)

    def test_present_packages_make_resolved_edge_count_increase(self):
        self.save("Vehicles/Parent.json", [])
        report = discover(self.root)
        self.assertEqual(report["resolved_edge_references"], 1)
        self.assertEqual(report["unresolved_edge_references"], 2)

    def test_array_reference_edge_types_are_grouped(self):
        self.save("Items/RifleComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Rifle_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Rifle_C", "Properties": {
                "GrenadeClasses": [
                    {"ObjectPath": "War/Content/Blueprints/Items/GasGrenade.0"},
                    {"ObjectPath": "War/Content/Blueprints/Items/FragGrenade.0"},
                ]}},
        ])
        report = discover(self.root)
        self.assertEqual(report["edge_type_counts"]["GrenadeClasses"], 2)

    def test_scan_max_files_bounds_crawl(self):
        with self.assertRaisesRegex(ValueError, "Too many"):
            discover(self.root, max_files=0)


if __name__ == "__main__":
    unittest.main()
