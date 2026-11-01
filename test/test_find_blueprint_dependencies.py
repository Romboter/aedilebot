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

    def test_scan_max_files_bounds_crawl(self):
        with self.assertRaisesRegex(ValueError, "Too many"):
            discover(self.root, max_files=0)


if __name__ == "__main__":
    unittest.main()
