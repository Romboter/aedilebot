"""Fail-closed original UE tag proof for case-only SCS component source identities."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.index_blueprint_graph import build_index
from scripts.resolve_scs_component_keys import resolve
from scripts.resolve_scs_typed_case_identity import parse_original_tags, review

INSPECTOR = "76ab955b5ad3ebffcdb9a8422c4225c17f9ec185"

class TypedSCSCaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {}}])
        self.put("Data/BPMountDynamicData.json", [{"Rows": {}}])
        self.put("Vehicles/Parent.json", [
            {"Name": "Parent_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "SCS_Node_3", "Type": "SCS_Node",
             "Properties": {"InternalVariableName": "ExhaustR", "VariableGuid": "guid-r"}},
        ])
        self.child = [
            {"Name": "Child_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Vehicles/Parent.1"}},
            {"Name": "InheritableComponentHandler", "Type": "InheritableComponentHandler",
             "Properties": {"Records": [{
                "ComponentKey": {
                    "OwnerClass": {"ObjectPath": "War/Content/Blueprints/Vehicles/Parent.1"},
                    "SCSVariableName": "exhaustR", "AssociatedGuid": "guid-r"},
                "ComponentTemplate": {"ObjectPath": "War/Content/Blueprints/Vehicles/Child.2"}},
             ]}},
        ]
        self.save()
        self.taglines = [
            ("SCSKEYTYPE","Vehicles/Child","InheritableComponentHandler","Records[0].ComponentKey.OwnerClass","ObjectProperty"),
            ("SCSKEYTYPE","Vehicles/Child","InheritableComponentHandler","Records[0].ComponentKey.SCSVariableName","NameProperty"),
            ("SCSKEYTYPE","Vehicles/Child","InheritableComponentHandler","Records[0].ComponentKey.AssociatedGuid","StructProperty"),
            ("SCSNODETYPE","Vehicles/Parent","SCS_Node_3","InternalVariableName","NameProperty"),
            ("SCSNODETYPE","Vehicles/Parent","SCS_Node_3","VariableGuid","StructProperty"),
        ]

    def put(self, rel, data):
        file = self.root / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data))

    def save(self):
        self.put("Vehicles/Child.json", self.child)

    def setup_evidence(self, entries=None):
        graph = build_index(self.root, "26058282")
        matched = resolve(self.root, graph)
        tags = entries if entries is not None else self.taglines
        text = "\n".join("\t".join([kind, "War/Content/Blueprints/" + package + ".uasset",
                                       record, field, tagtype])
                         for kind, package, record, field, tagtype in tags)
        evidence = parse_original_tags(text, graph, INSPECTOR)
        return graph, matched, evidence

    def test_typed_source_casefold_is_proven_but_runtime_not(self):
        graph, matched, evidence = self.setup_evidence()
        self.assertEqual(matched["coverage"]["counts"]["name_guid_disagreement"], 1)
        result = review(graph, matched, evidence)
        self.assertEqual(result["counts"], {"verified_typed_fname_case_only_source_identity": 1})
        self.assertEqual(result["reviewed_candidates"][0]["parent_scs_node"], "SCS_Node_3")
        self.assertEqual(result["reviewed_candidates"][0]["effective_runtime_component"], "not_established")
        self.assertFalse(result["safe_for_unattended_publication"])

    def test_wrong_original_name_property_type_is_denied(self):
        data = [(a,b,c,d,"StrProperty" if d.endswith("SCSVariableName") else t)
                for a,b,c,d,t in self.taglines]
        graph, matched, evidence = self.setup_evidence(data)
        self.assertEqual(review(graph,matched,evidence)["counts"], {"source_case_identity_unverified": 1})

    def test_missing_guid_type_is_denied(self):
        data = [x for x in self.taglines if x[3] != "VariableGuid"]
        graph, matched, evidence = self.setup_evidence(data)
        self.assertEqual(review(graph,matched,evidence)["counts"], {"source_case_identity_unverified": 1})

    def test_duplicate_tag_refused(self):
        graph, _, _ = self.setup_evidence()
        entries = self.taglines + [self.taglines[0]]
        text = "\n".join("\t".join([a,"War/Content/Blueprints/"+b+".uasset",c,d,t])
                         for a,b,c,d,t in entries)
        with self.assertRaisesRegex(ValueError,"Duplicated"):
            parse_original_tags(text, graph, INSPECTOR)

    def test_stale_tag_source_hash_rejected(self):
        graph, matched, evidence = self.setup_evidence()
        evidence["tags"][0]["source_sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError,"hash mismatch"):
            review(graph,matched,evidence)

    def test_changed_build_is_denied(self):
        graph, matched, evidence = self.setup_evidence()
        evidence["source_build_id"] = "different"
        with self.assertRaisesRegex(ValueError,"Unpinned"):
            review(graph,matched,evidence)

    def test_different_name_not_promoted_by_valid_types(self):
        self.child[1]["Properties"]["Records"][0]["ComponentKey"]["SCSVariableName"] = "AnotherName"
        self.save()
        graph, matched, evidence = self.setup_evidence()
        self.assertEqual(review(graph,matched,evidence)["counts"], {"source_case_identity_unverified": 1})

    def test_same_case_already_exact_not_reclassified(self):
        self.child[1]["Properties"]["Records"][0]["ComponentKey"]["SCSVariableName"] = "ExhaustR"
        self.save()
        graph, matched, evidence = self.setup_evidence()
        self.assertEqual(review(graph,matched,evidence)["reviewed_candidates"], [])

    def test_invalid_inspector_sha_refused(self):
        graph = build_index(self.root, "26058282")
        with self.assertRaisesRegex(ValueError,"Pinned inspector"):
            parse_original_tags("SCSNODETYPE", graph, "notsha")


if __name__ == "__main__":
    unittest.main()
