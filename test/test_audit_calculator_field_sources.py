"""Synthetic field-provenance inventory tests for calculator input research."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_calculator_field_sources import inspect, shape
from scripts.index_blueprint_graph import build_index


class CombatSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("Data/BPAmmoDynamicData.json", [{"Name": "AmmoTable", "Rows": {
            "RoundA": {"Damage": 100, "DamageType": "Explosive"},
        }}])
        self.write("Data/BPMountDynamicData.json", [{"Name": "MountTable", "Rows": {}}])
        self.write("DamageTypes/BPExplosive.json", [
            {"Name": "BPExplosive_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War.DamageType"}},
            {"Name": "Default__BPExplosive_C", "Type": "BPExplosive_C",
             "Properties": {"DamageMultiplier": 0.75, "Source": "test"}},
        ])
        self.write("Structures/BPPillbox.json", [
            {"Name": "BPPillbox_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Structures/BPBase.0"}},
            {"Name": "Default__BPPillbox_C", "Type": "BPPillbox_C",
             "Properties": {"Health": 1500, "ArmourType": "Tier2Structure",
                            "Tags": ["not-combat"]}},
            {"Name": "AIGun", "Type": "AIGunTurretComponent",
             "Properties": {"DamageAttributes": {"Damage": 22, "Range": 30}}},
        ])
        self.write("Structures/BPBase.json", [
            {"Name": "BPBase_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War.Structure"}},
            {"Name": "Default__BPBase_C", "Type": "BPBase_C",
             "Properties": {}},
        ])
        self.write("Vehicles/BPJeep.json", [
            {"Name": "BPJeep_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War.Vehicle"}},
            {"Name": "Default__BPJeep_C", "Type": "BPJeep_C",
             "Properties": {"Health": 800, "MaxHealth": 800}},
        ])

    def write(self, path, data):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data), encoding="utf-8")

    def test_all_critical_surface_shapes_kept_source_only(self):
        out = inspect(self.root, build_index(self.root, "26058282"))
        self.assertFalse(out["safe_for_unattended_publication"])
        self.assertEqual(out["coverage"]["roots"]["DamageTypes"]["packages"], 1)
        self.assertEqual(out["coverage"]["roots"]["Structures"]["packages"], 2)
        self.assertEqual(out["coverage"]["roots"]["Data"]["table_rows"], 1)
        self.assertEqual(out["coverage"]["roots"]["Data"]["table_exports"], 2)
        self.assertEqual(out["coverage"]["roots"]["Vehicles"]["packages"], 1)
        damage = out["damage_type_class_source_identities"]
        self.assertEqual(len(damage), 1)
        self.assertEqual(damage[0]["parent_status"], "non_blueprint_parent_or_missing")
        health = next(x for x in out["source_field_records"]
                      if x["package"] == "Structures/BPPillbox" and x["field"] == "Health")
        self.assertEqual(health["shape"], "number")
        self.assertEqual(health["role"], "saved_default")
        self.assertEqual(health["runtime_effective"], "not_established")
        self.assertEqual(len(health["saved_field_value_sha256"]), 64)
        turret = next(x for x in out["source_field_records"]
                      if x["field"] == "DamageAttributes")
        self.assertEqual(turret["nested_saved_keys"], ["Damage", "Range"])
        self.assertEqual(turret["role"], "component_template")
        self.assertTrue(any(x["table_package"] == "Data/BPAmmoDynamicData"
                            and x["field"] == "Damage" for x in out["table_row_field_shapes"]))

    def test_changed_source_hash_aborts(self):
        graph = build_index(self.root, "26058282")
        target = self.root / "DamageTypes/BPExplosive.json"
        target.write_text(target.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "hash"):
            inspect(self.root, graph)

    def test_changed_relation_digest_aborts(self):
        graph = build_index(self.root, "26058282")
        graph["object_references"].clear()
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            inspect(self.root, graph)

    def test_saved_field_scan_bound(self):
        graph = build_index(self.root, "26058282")
        with self.assertRaisesRegex(ValueError, "bound"):
            inspect(self.root, graph, max_source_fields=1)

    def test_shapes_distinguish_null_bool_scalar_and_object_reference(self):
        self.assertEqual(shape(None), "null")
        self.assertEqual(shape(True), "boolean")
        self.assertEqual(shape(12), "number")
        self.assertEqual(shape("12"), "string")
        self.assertEqual(shape([]), "array")
        self.assertEqual(shape({"a": 1}), "struct")
        self.assertEqual(shape({"ObjectPath": "War/Content/Blueprints/Items/Gun.0"}), "object_reference")


if __name__ == "__main__":
    unittest.main()
