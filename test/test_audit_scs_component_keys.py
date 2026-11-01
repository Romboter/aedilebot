"""Synthetic tests for SCS handler-key source shape inspection."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.audit_scs_component_keys import inspect
from scripts.index_blueprint_graph import build_index


class SCSKeyAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {}}])
        self.put("Data/BPMountDynamicData.json", [{"Rows": {}}])
        self.put("Items/Parent.json", [
            {"Name": "Parent_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Node0", "Type": "SCS_Node", "Properties": {
                "VariableName": "CannonMount", "VariableGuid": {"A": 1, "B": 2}}},
            {"Name": "Node1", "Type": "SCS_Node", "Properties": {
                "VariableName": "OtherMount", "VariableGuid": {"A": 4, "B": 5}}},
        ])
        self.child = [
            {"Name": "Child_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Items/Parent.1"}},
            {"Name": "Handler", "Type": "InheritableComponentHandler",
             "Properties": {"Records": [
                 {"ComponentKey": {
                     "OwnerClass": {"ObjectPath": "War/Content/Blueprints/Items/Parent.1"},
                     "SCSVariableName": "CannonMount",
                     "AssociatedGuid": {"A": 1, "B": 2}},
                  "ComponentTemplate": {"ObjectPath": "War/Content/Blueprints/Items/Child.3"}}
             ]}},
        ]
        self.save_child()

    def put(self, rel, obj):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj), encoding="utf-8")

    def save_child(self):
        self.put("Items/Child.json", self.child)

    def scan(self, graph=None):
        return inspect(self.root, graph or build_index(self.root, "26058282"))

    def test_key_shapes_are_only_candidate_evidence(self):
        result = self.scan()
        self.assertEqual(result["counts"]["source_pairs_checked"], 1)
        self.assertEqual(result["counts"]["same_name_node_unique_candidate"], 1)
        self.assertEqual(result["handler_key_field_counts"]["AssociatedGuid"], 1)
        self.assertEqual(result["owner_scs_node_field_counts"]["VariableGuid"], 2)
        self.assertEqual(result["bounded_examples"][0]["key_variable_name"], "CannonMount")
        self.assertEqual(result["status"], "review_only_scs_key_shape_diagnostic")
        self.assertFalse(result["safe_for_unattended_publication"])
        self.assertNotIn("effective_component", result)

    def test_ambiguous_name_is_not_promoted(self):
        parent = json.loads((self.root / "Items/Parent.json").read_text())
        parent[2]["Properties"]["VariableName"] = "CannonMount"
        self.put("Items/Parent.json", parent)
        result = self.scan()
        self.assertEqual(result["counts"]["same_name_node_ambiguous"], 1)
        self.assertNotIn("same_name_node_unique_candidate", result["counts"])

    def test_missing_name_remains_unresolved(self):
        self.child[1]["Properties"]["Records"][0]["ComponentKey"].pop("SCSVariableName")
        self.save_child()
        result = self.scan()
        self.assertEqual(result["counts"]["key_name_absent_or_non_string"], 1)

    def test_tampered_source_hash_is_rejected(self):
        graph = build_index(self.root, "26058282")
        self.child[1]["Properties"]["Records"][0]["ComponentKey"]["SCSVariableName"] = "OtherMount"
        self.save_child()
        with self.assertRaisesRegex(ValueError, "hash"):
            self.scan(graph)

    def test_missing_record_fails_closed(self):
        graph = build_index(self.root, "26058282")
        self.child[1]["Properties"]["Records"] = []
        self.save_child()
        with self.assertRaisesRegex(ValueError, "hash"):
            self.scan(graph)


if __name__ == "__main__":
    unittest.main()
