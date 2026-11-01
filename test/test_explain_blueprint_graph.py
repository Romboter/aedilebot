"""Synthetic tests for explaining actual referenced Blueprint package chains."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.index_blueprint_graph import build_index
from scripts.explain_blueprint_graph import explain


class ExplainGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {
            "MGAmmo": {"Damage": 55},
        }}])
        self.write("Data/BPMountDynamicData.json", [{"Rows": {
            "TankGunnerC": {"DamageMultiplier": 1.2},
        }}])
        self.write("Vehicles/Child.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Child_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Vehicles/Base.1"}},
            {"Name": "Default__Child_C", "Properties": {}},
        ])
        self.write("Vehicles/Base.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Base_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Base_C", "Properties": {"CodeName": "TankC"}},
            {"Type": "VehicleSeatComponent", "Name": "GunnerSeat1_GEN_VARIABLE",
             "Properties": {
                "MountCodeName": "TankGunnerC",
                "MountComponent": {"ObjectPath": "War/Content/Blueprints/Vehicles/GunnerComponent.0"},
            }},
        ])
        self.write("Vehicles/GunnerComponent.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Gunner_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Gunner_C", "Properties": {
                "AmmoName": "MGAmmo",
                "ProjectileClass": {"ObjectPath": "War/Content/Blueprints/Items/MissingProjectile.0"},
            }},
        ])

    def write(self, name, content):
        p = self.root / name
        p.parent.mkdir(exist_ok=True, parents=True)
        p.write_text(json.dumps(content), encoding="utf-8")

    def graph(self):
        return build_index(self.root, "26058282")

    def test_inherited_seat_to_mount_to_ammo_is_traceable_without_guessing(self):
        out = explain(self.graph(), "Vehicles/Child")
        self.assertEqual(out["status"], "explicit_graph_with_unresolved_references")
        self.assertEqual(len(out["packages"]), 3)
        gunner = next(x for x in out["packages"] if x["package"] == "Vehicles/GunnerComponent")
        self.assertEqual([x["field"] for x in gunner["source_path"]],
                         ["SuperStruct", "MountComponent"])
        self.assertEqual(gunner["depth"], 2)
        ammo = [x for x in out["numeric_row_references"] if x["row"] == "MGAmmo"]
        self.assertEqual(len(ammo), 1)
        self.assertEqual(ammo[0]["status"], "row_present")
        self.assertEqual(out["gaps"]["missing_export_links"][0]["target"], "Items/MissingProjectile")
        self.assertFalse(out["safe_for_unattended_publication"])
        self.assertNotIn("damage", out)

    def test_reduced_depth_marks_partial_not_complete(self):
        out = explain(self.graph(), "Vehicles/Child", max_depth=1)
        self.assertEqual(out["status"], "bounded_partial_explicit_graph")
        self.assertEqual(len(out["packages"]), 2)
        self.assertEqual(out["gaps"]["edges_not_traversed_due_to_depth_limit"], 1)

    def test_node_limit_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Maximum reachable"):
            explain(self.graph(), "Vehicles/Child", max_nodes=2)

    def test_closed_graph_does_not_authorize_publication(self):
        self.write("Items/MissingProjectile.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Projectile_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Projectile_C", "Properties": {}},
        ])
        out = explain(self.graph(), "Vehicles/Child")
        self.assertEqual(out["status"], "explicit_graph_closure_for_recognized_edges")
        self.assertFalse(out["safe_for_unattended_publication"])
        self.assertEqual(out["gaps"]["missing_export_links"], [])

    def test_invalid_source_package_rejected(self):
        with self.assertRaisesRegex(ValueError, "absent"):
            explain(self.graph(), "Vehicles/Unknown")


if __name__ == "__main__":
    unittest.main()
