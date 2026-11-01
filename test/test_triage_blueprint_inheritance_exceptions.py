"""Synthetic tests for exact parent/child seat and MultiAmmo graph investigation."""
from pathlib import Path
import json
import tempfile
import unittest

from scripts.index_blueprint_graph import build_index
from scripts.triage_blueprint_inheritance_exceptions import inspect, lineage, parent_graph


class InheritanceTriageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {
            "SmokeAmmo": {"Damage": 0},
            "MGAmmo": {"Damage": 65},
        }}])
        self.put("Data/BPMountDynamicData.json", [{"Rows": {
            "ActualGunner": {"DamageMultiplier": 1.1},
        }}])
        self.put("Vehicles/Base.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Base_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Base_C", "Properties": {}},
            {"Type": "VehicleSeatComponent", "Name": "GunnerSeat1_GEN_VARIABLE",
             "Properties": {
                 "MountCodeName": "MissingBaseGunner",
                 "MountComponent": {"ObjectPath": "War/Content/Blueprints/Items/BaseGun.0"},
             }},
        ])
        self.put("Vehicles/Child.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Child_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Vehicles/Base.1"}},
            {"Name": "Default__Child_C", "Properties": {}},
            {"Type": "VehicleSeatComponent", "Name": "GunnerSeat1_GEN_VARIABLE",
             "Properties": {"MountCodeName": "ActualGunner"}},
        ])
        self.put("Vehicles/OtherChild.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "OtherChild_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Vehicles/Base.1"}},
            {"Name": "Default__OtherChild_C", "Properties": {}},
        ])
        self.put("Items/AmmoBase.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "AmmoBase_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__AmmoBase_C", "Properties": {"MultiAmmo": None}},
        ])
        self.put("Items/AmmoChild.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "AmmoChild_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Items/AmmoBase.1"}},
            {"Name": "Default__AmmoChild_C", "Properties": {
                "MultiAmmo": {"CompatibleAmmoNames": ["SmokeAmmo", "MGAmmo"]},
            }},
        ])
        self.put("Items/AmmoSecondChild.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "AmmoSecondChild_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Items/AmmoBase.1"}},
            {"Name": "Default__AmmoSecondChild_C", "Properties": {
                "AmmoName": "MGAmmo",
            }},
        ])

    def put(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content), encoding="utf-8")

    def report(self, mount_base="Vehicles/Base", ammo_base="Items/AmmoBase"):
        graph = build_index(self.root, "26058282")
        return inspect(self.root, graph,
                       mount_targets=((mount_base, "GunnerSeat1_GEN_VARIABLE", "MissingBaseGunner"),),
                       ammo_targets=(ammo_base,))

    def test_base_mount_is_overridden_in_one_descendant_not_other(self):
        case = self.report()["mount_cases"][0]
        observed = {x["package"]: x for x in case["descendants"]}
        self.assertEqual(observed["Vehicles/Base"]["status"], "named_mount_row_missing")
        self.assertTrue(observed["Vehicles/Base"]["effective_mount_is_inherited_from_base"])
        self.assertEqual(observed["Vehicles/Child"]["mount_code_name"], "ActualGunner")
        self.assertEqual(observed["Vehicles/Child"]["status"], "named_mount_row_present")
        self.assertFalse(observed["Vehicles/Child"]["effective_mount_is_inherited_from_base"])
        self.assertEqual(observed["Vehicles/Child"]["mount_identity_provenance"]["asset"],
                         "Vehicles/Child.json")
        self.assertEqual(observed["Vehicles/OtherChild"]["status"], "named_mount_row_missing")
        self.assertTrue(observed["Vehicles/OtherChild"]["effective_mount_is_inherited_from_base"])
        self.assertFalse(self.report()["safe_for_unattended_publication"])

    def test_inherited_null_and_child_valid_options_remain_distinct(self):
        case = self.report()["multi_ammo_cases"][0]
        observed = {x["package"]: x for x in case["subclasses"]}
        self.assertEqual(observed["Items/AmmoBase"]["effective_multi_ammo"]["status"],
                         "explicit_none_or_missing")
        self.assertEqual(observed["Items/AmmoChild"]["effective_multi_ammo"]["status"],
                         "explicit_ammo_options")
        self.assertEqual(observed["Items/AmmoChild"]["effective_multi_ammo"]["ammo_options"],
                         ["SmokeAmmo", "MGAmmo"])
        self.assertEqual(observed["Items/AmmoSecondChild"]["effective_multi_ammo"]["status"],
                         "explicit_none_or_missing")
        self.assertEqual(observed["Items/AmmoSecondChild"]["other_explicit_field_evidence"][0]["field"],
                         "AmmoName")
        self.assertEqual(len(case["declarations_in_ancestry"]), 1)

    def test_inherited_default_option_is_not_falsely_missing(self):
        self.put("Items/AmmoBase.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "AmmoBase_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__AmmoBase_C", "Properties": {
                "MultiAmmo": {"CompatibleAmmoNames": ["MGAmmo"]},
            }},
        ])
        case = self.report()["multi_ammo_cases"][0]
        values = {x["package"]: x["effective_multi_ammo"]
                  for x in case["subclasses"]}
        self.assertEqual(values["Items/AmmoSecondChild"]["source"], "Items/AmmoBase")
        self.assertEqual(values["Items/AmmoSecondChild"]["status"], "explicit_ammo_options")

    def test_source_hash_mismatch_aborts(self):
        graph = build_index(self.root, "26058282")
        self.put("Vehicles/Child.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Child_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Vehicles/Base.1"}},
            {"Name": "Default__Child_C", "Properties": {"ExtraField": True}},
        ])
        with self.assertRaisesRegex(ValueError, "source hash"):
            inspect(self.root, graph,
                    mount_targets=(("Vehicles/Base", "GunnerSeat1_GEN_VARIABLE", "MissingBaseGunner"),),
                    ammo_targets=())

    def test_missing_target_fails_closed(self):
        graph = build_index(self.root, "26058282")
        with self.assertRaisesRegex(ValueError, "Missing target"):
            inspect(self.root, graph, mount_targets=(("Vehicles/Absent", "seat", "mount"),),
                    ammo_targets=())

    def test_parent_cycle_rejected(self):
        graph = build_index(self.root, "26058282")
        parents, children = parent_graph(graph)
        parents["Vehicles/Base"] = "Vehicles/Child"
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            lineage("Vehicles/Base", parents,
                    {entry["package"]: entry["sha256"] for entry in graph["packages"]})


if __name__ == "__main__":
    unittest.main()
