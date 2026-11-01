"""Synthetic tests for explicit inheritable-component record links."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.index_blueprint_graph import build_index
from scripts.audit_blueprint_reference_surface import scan

class HandlerReferences(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {}}])
        self.write("Data/BPMountDynamicData.json", [{"Rows": {}}])
        self.write("Items/Base.json", [
            {"Name": "Base_C", "Type": "BlueprintGeneratedClass", "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Base_C", "Properties": {}}])
        self.child = [
            {"Name": "Child_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Items/Base.1"}},
            {"Name": "Default__Child_C", "Properties": {}},
            {"Name": "Handler", "Type": "InheritableComponentHandler",
             "Properties": {"Records": [
                 {"ComponentKey": {"OwnerClass": {"ObjectPath": "War/Content/Blueprints/Items/Base.1"}},
                  "ComponentTemplate": {"ObjectPath": "War/Content/Blueprints/Items/Child.3"}},
                 {"ComponentKey": {"OwnerClass": {"ObjectPath": "/Script/War.Native"}},
                  "ComponentTemplate": {"ObjectPath": "War/Content/Blueprints/Items/Child.4"}},
             ]}}]
        self.save_child()

    def write(self, name, value):
        file = self.root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(value))

    def save_child(self):
        self.write("Items/Child.json", self.child)

    def test_index_and_full_reference_reconciliation(self):
        graph = build_index(self.root, "26058282")
        pairs = {(e["field"], e["target"]) for e in graph["object_references"]}
        self.assertIn(("Records[0].ComponentKey.OwnerClass", "Items/Base"), pairs)
        self.assertIn(("Records[0].ComponentTemplate", "Items/Child"), pairs)
        self.assertIn(("Records[1].ComponentTemplate", "Items/Child"), pairs)
        self.assertEqual(len(graph["object_references"]), 4)
        self.assertEqual(scan(self.root, graph)["indexed_edges_verified"], 4)

    def test_retarget_changes_fingerprint(self):
        before = build_index(self.root, "26058282")
        self.child[-1]["Properties"]["Records"][0]["ComponentKey"]["OwnerClass"]["ObjectPath"] = (
            "War/Content/Blueprints/Items/Child.1")
        self.save_child()
        self.assertNotEqual(before["relation_digest"],
                            build_index(self.root, "26058282")["relation_digest"])

    def test_invalid_records_and_keys_rejected(self):
        records = self.child[-1]["Properties"]["Records"]
        for invalid in ("bad", [23], [{"ComponentKey": 9}]):
            self.child[-1]["Properties"]["Records"] = invalid
            self.save_child()
            with self.assertRaisesRegex(ValueError, "Invalid component"):
                build_index(self.root, "26058282")
        self.child[-1]["Properties"]["Records"] = records

if __name__ == "__main__":
    unittest.main()
