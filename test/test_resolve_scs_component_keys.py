"""Synthetic exact SCS key matching: no runtime CDO inference."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.index_blueprint_graph import build_index
from scripts.resolve_scs_component_keys import resolve


class ExactSCSKeyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {}}])
        self.put("Data/BPMountDynamicData.json", [{"Rows": {}}])
        self.parent = [
            {"Name": "Parent_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "NodeA", "Type": "SCS_Node",
             "Properties": {"InternalVariableName": "Gun", "VariableGuid": "guid-a",
                            "ComponentTemplate": {"ObjectPath": "War/Content/Blueprints/Items/Parent.9"}}},
            {"Name": "NodeB", "Type": "SCS_Node",
             "Properties": {"InternalVariableName": "Gun", "VariableGuid": "guid-b"}},
        ]
        self.child = [
            {"Name": "Child_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Items/Parent.1"}},
            {"Name": "Handler", "Type": "InheritableComponentHandler",
             "Properties": {"Records": [{
                "ComponentKey": {
                    "OwnerClass": {"ObjectPath": "War/Content/Blueprints/Items/Parent.1"},
                    "SCSVariableName": "Gun", "AssociatedGuid": "guid-a"},
                "ComponentTemplate": {"ObjectPath": "War/Content/Blueprints/Items/Child.2"}},
             ]}},
        ]
        self.save()

    def put(self, rel, data):
        file = self.root / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data))

    def save(self):
        self.put("Items/Parent.json", self.parent)
        self.put("Items/Child.json", self.child)

    def result(self):
        return resolve(self.root, build_index(self.root, "26058282"))

    def test_same_name_different_guids_unique_exact_match(self):
        r = self.result()
        self.assertEqual(r["coverage"]["counts"], {"unique_serialized_key_match": 1})
        hit = r["records"][0]
        self.assertEqual(hit["candidate_counts"], {"name": 2, "guid": 1, "exact": 1})
        self.assertEqual(hit["parent_scs_match"]["scs_node_record"], "NodeA")
        self.assertEqual(hit["effective_runtime_component"], "not_established")
        self.assertEqual(hit["original_property_types"], "not_independently_verified")
        self.assertFalse(r["safe_for_unattended_publication"])

    def test_guid_mismatch_with_name_match_never_falls_back(self):
        self.child[-1]["Properties"]["Records"][0]["ComponentKey"]["AssociatedGuid"] = "no-such-guid"
        self.save()
        result = self.result()["records"][0]
        self.assertEqual(result["status"], "name_guid_disagreement")
        self.assertIsNone(result["parent_scs_match"])

    def test_name_mismatch_with_guid_match_never_falls_back(self):
        self.child[-1]["Properties"]["Records"][0]["ComponentKey"]["SCSVariableName"] = "NoGun"
        self.save()
        self.assertEqual(self.result()["records"][0]["status"], "name_guid_disagreement")

    def test_guid_only_diagnostic_does_not_resolve_renamed_component(self):
        self.child[-1]["Properties"]["Records"][0]["ComponentKey"]["SCSVariableName"] = "RenamedGun"
        self.save()
        result = self.result()["records"][0]
        self.assertEqual(result["status"], "name_guid_disagreement")
        self.assertIsNone(result["parent_scs_match"])
        evidence = result["guid_only_diagnostic"]
        self.assertEqual(evidence["parent_scs_node_record"], "NodeA")
        self.assertEqual(evidence["parent_saved_variable_name"], "Gun")
        self.assertEqual(evidence["child_saved_key_name"], "RenamedGun")
        self.assertFalse(evidence["accepted_as_exact_match"])
        self.assertEqual(result["effective_runtime_component"], "not_established")

    def test_duplicate_exact_name_and_guid_remains_ambiguous(self):
        self.parent[2]["Properties"]["VariableGuid"] = "guid-a"
        self.save()
        self.assertEqual(self.result()["records"][0]["status"], "ambiguous_exact_key")

    def test_absent_key_never_resolves(self):
        self.child[-1]["Properties"]["Records"][0]["ComponentKey"]["AssociatedGuid"] = None
        self.save()
        self.assertEqual(self.result()["records"][0]["status"], "invalid_component_key")

    def test_no_parent_node_match(self):
        self.child[-1]["Properties"]["Records"][0]["ComponentKey"].update(
            SCSVariableName="NoGun", AssociatedGuid="no-such-guid")
        self.save()
        self.assertEqual(self.result()["records"][0]["status"], "no_parent_scs_match")

    def test_hash_mismatch_refuses_stale_build(self):
        index = build_index(self.root, "26058282")
        self.parent[1]["Properties"]["InternalVariableName"] = "Changed"
        self.save()
        with self.assertRaisesRegex(ValueError, "hash"):
            resolve(self.root, index)

    def test_duplicate_handler_name_is_ambiguous(self):
        self.child.append(self.child[-1].copy())
        self.save()
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            self.result()


if __name__ == "__main__":
    unittest.main()
