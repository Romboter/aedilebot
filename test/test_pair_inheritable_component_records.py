"""Synthetic tests for serialized handler record pairing."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.index_blueprint_graph import build_index
from scripts.pair_inheritable_component_records import pair_records

class PairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {}}])
        self.put("Data/BPMountDynamicData.json", [{"Rows": {}}])
        self.put("Items/Base.json", [{"Name": "Base_C", "Type": "BlueprintGeneratedClass",
                                      "SuperStruct": {"ObjectPath": "/Script/War"}}])
        self.put("Items/Child.json", [
            {"Name": "Child_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Items/Base.1"}},
            {"Name": "Handler", "Type": "InheritableComponentHandler",
             "Properties": {"Records": [
               {"ComponentKey": {"OwnerClass": {"ObjectPath": "War/Content/Blueprints/Items/Base.1"}},
                "ComponentTemplate": {"ObjectPath": "War/Content/Blueprints/Items/Child.2"}},
               {"ComponentKey": {"OwnerClass": {"ObjectPath": "/Script/War.Native"}},
                "ComponentTemplate": {"ObjectPath": "War/Content/Blueprints/Items/Child.3"}},
            ]}},
        ])

    def put(self, path, data):
        f = self.root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data))

    def test_exact_paired_fields_and_native_unknown(self):
        r = pair_records(build_index(self.root, "26058282"))
        self.assertEqual(len(r["records"]), 2)
        self.assertEqual(r["records"][0]["owner_class"]["target_package"], "Items/Base")
        self.assertEqual(r["records"][0]["component_template"]["target_package"], "Items/Child")
        self.assertEqual(r["records"][1]["status"], "template_only_native_or_missing_owner")
        self.assertIsNone(r["records"][1]["owner_class"])
        self.assertEqual(r["coverage"]["source_status_counts"]["template_same_package"], 2)
        self.assertFalse(r["safe_for_unattended_publication"])

    def test_bad_source_hash_fails(self):
        g = build_index(self.root, "26058282")
        next(x for x in g["packages"] if x["package"] == "Items/Child")["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source hash"):
            pair_records(g)

    def test_record_order_changes_source_association(self):
        p = self.root / "Items/Child.json"
        before = pair_records(build_index(self.root, "26058282"))
        data = json.loads(p.read_text())
        data[-1]["Properties"]["Records"].reverse()
        self.put("Items/Child.json", data)
        after = pair_records(build_index(self.root, "26058282"))
        self.assertNotEqual(before["records"], after["records"])

if __name__ == "__main__":
    unittest.main()
