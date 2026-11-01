"""Synthetic source field-delta tests; never infer effective component defaults."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.index_blueprint_graph import build_index
from scripts.resolve_scs_component_keys import resolve
from scripts.audit_scs_template_exports import inspect as audit_templates
from scripts.resolve_qualified_scs_template_exports import inspect as qualified
from scripts.audit_scs_template_field_deltas import analyze


class SerializedTemplateFieldTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.put("Data/BPAmmoDynamicData.json",[{"Rows":{}}])
        self.put("Data/BPMountDynamicData.json",[{"Rows":{}}])
        self.parent=[
            {"Name":"Parent_C","Type":"BlueprintGeneratedClass","SuperStruct":{"ObjectPath":"/Script/War"}},
            {"Name":"SCS_Node_1","Type":"SCS_Node","Properties":{
                "InternalVariableName":"Gun","VariableGuid":"GUID-1",
                "ComponentTemplate":{"ObjectName":"MeshComponent'Parent_C:ParentMesh'",
                                     "ObjectPath":"War/Content/Blueprints/Items/Parent.3"}}},
            {"Name":"ParentMesh","Type":"MeshComponent",
             "Outer":{"ObjectName":"BlueprintGeneratedClass'Parent_C'",
                      "ObjectPath":"War/Content/Blueprints/Items/Parent.1"},
             "Properties":{"ParentOnly":123,"SharedChanged":{"X":1},
                           "Same":5}},
        ]
        self.child=[
            {"Name":"Child_C","Type":"BlueprintGeneratedClass",
             "SuperStruct":{"ObjectPath":"War/Content/Blueprints/Items/Parent.1"}},
            {"Name":"Handler","Type":"InheritableComponentHandler",
             "Properties":{"Records":[{
                "ComponentKey":{"OwnerClass":{"ObjectPath":"War/Content/Blueprints/Items/Parent.1"},
                                "SCSVariableName":"Gun","AssociatedGuid":"GUID-1"},
                "ComponentTemplate":{"ObjectName":"MeshComponent'Child_C:ChildMesh'",
                                     "ObjectPath":"War/Content/Blueprints/Items/Child.3"}}]}},
            {"Name":"ChildMesh","Type":"MeshComponent",
             "Outer":{"ObjectName":"BlueprintGeneratedClass'Child_C'",
                      "ObjectPath":"War/Content/Blueprints/Items/Child.1"},
             "Properties":{"ChildOnly":True,"SharedChanged":{"X":2},
                           "Same":5}},
        ]
        self.save()

    def put(self,path,blob):
        file=self.root/path
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(blob))

    def save(self):
        self.put("Items/Parent.json",self.parent)
        self.put("Items/Child.json",self.child)

    def source(self):
        index=build_index(self.root,"26058282")
        base=resolve(self.root,index)
        typed={"source_build_id":index["source_build_id"],
               "relation_digest":index["relation_digest"],
               "status":"review_only_type_gated_scs_case_identity",
               "safe_for_unattended_publication":False,
               "reviewed_candidates":[]}
        refs=audit_templates(self.root,index,base,typed)
        return index,qualified(self.root,index,refs)

    def test_four_declared_field_categories_remain_source_only(self):
        graph,ids=self.source()
        report=analyze(self.root,graph,ids)
        record=report["records"][0]
        self.assertEqual(record["explicit_child_only_fields"],["ChildOnly"])
        self.assertEqual(record["explicit_parent_only_fields"],["ParentOnly"])
        self.assertEqual(record["explicit_shared_changed_fields"],["SharedChanged"])
        self.assertEqual(record["explicit_shared_equal_fields"],["Same"])
        self.assertEqual(record["effective_runtime_component"],"not_established")
        self.assertEqual(report["coverage"]["counts"]["source_pairs_compared"],1)
        self.assertFalse(report["safe_for_unattended_publication"])

    def test_parent_omission_is_not_published_as_effective_inheritance(self):
        graph,ids=self.source()
        report=analyze(self.root,graph,ids)
        self.assertNotIn("effective_parent_fields",report["records"][0])
        self.assertIn("NOT reconstructed",report["limitations"][0])

    def test_non_dict_saved_props_fail_closed(self):
        self.child[-1]["Properties"]=["bad"]
        self.save()
        graph,ids=self.source()
        with self.assertRaisesRegex(ValueError,"Malformed component properties"):
            analyze(self.root,graph,ids)

    def test_source_file_modified_after_indexing_fails(self):
        graph,ids=self.source()
        self.parent[-1]["Properties"]["Same"]=999
        self.save()
        with self.assertRaisesRegex(ValueError,"hash"):
            analyze(self.root,graph,ids)

    def test_unverified_outer_owner_cannot_enter_delta(self):
        graph,ids=self.source()
        ids["records"][0]["child_component"]["outer_source_provenance"]["status"]="outer_mismatch"
        with self.assertRaisesRegex(ValueError,"Unverified component"):
            analyze(self.root,graph,ids)

    def test_tampered_relation_digest_fails(self):
        graph,ids=self.source()
        ids["relation_digest"]="tampered"
        with self.assertRaisesRegex(ValueError,"Unpinned"):
            analyze(self.root,graph,ids)

if __name__=="__main__":
    unittest.main()
