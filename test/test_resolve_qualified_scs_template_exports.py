"""Source-only tests for class-qualified SCS component template export identities."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.index_blueprint_graph import build_index
from scripts.resolve_scs_component_keys import resolve
from scripts.audit_scs_template_exports import inspect as inspect_template_refs
from scripts.resolve_qualified_scs_template_exports import inspect as match_qualified


class QualifiedSCSExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.put("Data/BPAmmoDynamicData.json",[{"Rows":{}}])
        self.put("Data/BPMountDynamicData.json",[{"Rows":{}}])
        self.parent=[
            {"Name":"Parent_C","Type":"BlueprintGeneratedClass",
             "SuperStruct":{"ObjectPath":"/Script/War"}},
            {"Name":"SCS_Node_1","Type":"SCS_Node","Properties":{
                "InternalVariableName":"Cannon","VariableGuid":"guid1",
                "ComponentTemplate":{"ObjectPath":"War/Content/Blueprints/Items/Parent.3",
                                     "ObjectName":"StaticMeshComponent'Parent_C:ParentMesh'"}}},
            {"Name":"ParentMesh","Type":"StaticMeshComponent",
             "Outer":{"ObjectName":"BlueprintGeneratedClass'Parent_C'",
                      "ObjectPath":"War/Content/Blueprints/Items/Parent.1"}}
        ]
        self.child=[
            {"Name":"Child_C","Type":"BlueprintGeneratedClass",
             "SuperStruct":{"ObjectPath":"War/Content/Blueprints/Items/Parent.1"}},
            {"Name":"Handler","Type":"InheritableComponentHandler","Properties":{"Records":[{
                "ComponentKey":{
                    "OwnerClass":{"ObjectPath":"War/Content/Blueprints/Items/Parent.1"},
                    "SCSVariableName":"Cannon","AssociatedGuid":"guid1"},
                "ComponentTemplate":{"ObjectPath":"War/Content/Blueprints/Items/Child.3",
                                     "ObjectName":"StaticMeshComponent'Child_C:ChildMesh'"}}]}},
            {"Name":"ChildMesh","Type":"StaticMeshComponent",
             "Outer":{"ObjectName":"BlueprintGeneratedClass'Child_C'",
                      "ObjectPath":"War/Content/Blueprints/Items/Child.1"}}
        ]
        self.save()

    def put(self,path,value):
        dst=self.root/path
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_text(json.dumps(value),encoding="utf-8")

    def save(self):
        self.put("Items/Parent.json",self.parent)
        self.put("Items/Child.json",self.child)

    def report(self):
        graph=build_index(self.root,"26058282")
        base=resolve(self.root,graph)
        typed={
            "source_build_id":graph["source_build_id"],
            "relation_digest":graph["relation_digest"],
            "status":"review_only_type_gated_scs_case_identity",
            "safe_for_unattended_publication":False,
            "reviewed_candidates":[]
        }
        refs=inspect_template_refs(self.root,graph,base,typed)
        return graph,refs

    def test_unique_class_export_and_type(self):
        graph,refs=self.report()
        out=match_qualified(self.root,graph,refs)
        self.assertEqual(out["coverage"]["status_counts"],{
            "child_qualified_source_export_unique":1,
            "parent_qualified_source_export_unique":1,
        })
        record=out["records"][0]
        self.assertEqual(record["parent_component"]["component_name"],"ParentMesh")
        self.assertEqual(record["child_component"]["component_name"],"ChildMesh")
        self.assertEqual(record["child_component"]["component_type"],"StaticMeshComponent")
        self.assertEqual(record["effective_runtime_component"],"not_established")
        self.assertFalse(out["safe_for_unattended_publication"])

    def test_missing_exact_component_name_does_not_guess_numeric_suffix(self):
        self.child[-1]["Name"]="Different"
        self.save()
        graph,refs=self.report()
        out=match_qualified(self.root,graph,refs)
        self.assertEqual(out["records"][0]["child_component"]["status"],"component_export_not_found")

    def test_class_name_not_exported_is_unresolved(self):
        ref=self.child[1]["Properties"]["Records"][0]["ComponentTemplate"]
        ref["ObjectName"]="StaticMeshComponent'Missing_C:ChildMesh'"
        self.save()
        graph,refs=self.report()
        self.assertEqual(match_qualified(self.root,graph,refs)["records"][0]["child_component"]["status"],
                         "generated_class_not_exported")

    def test_wrong_component_type_does_not_silently_resolve(self):
        ref=self.child[1]["Properties"]["Records"][0]["ComponentTemplate"]
        ref["ObjectName"]="SkeletalMeshComponent'Child_C:ChildMesh'"
        self.save()
        graph,refs=self.report()
        self.assertEqual(match_qualified(self.root,graph,refs)["records"][0]["child_component"]["status"],
                         "component_export_not_found")

    def test_ambiguous_export_name_is_unresolved(self):
        self.parent.append(dict(self.parent[-1]))
        self.save()
        graph,refs=self.report()
        self.assertEqual(match_qualified(self.root,graph,refs)["records"][0]["parent_component"]["status"],
                         "component_export_ambiguous")

    def test_invalid_qualified_name_not_guessed(self):
        self.parent[1]["Properties"]["ComponentTemplate"]["ObjectName"]="ParentMesh"
        self.save()
        graph,refs=self.report()
        self.assertEqual(match_qualified(self.root,graph,refs)["records"][0]["parent_component"]["status"],
                         "unsupported_qualified_object_name")

    def test_export_outer_confirms_expected_generated_class(self):
        graph,refs=self.report()
        out=match_qualified(self.root,graph,refs)
        row=out["records"][0]
        for side in ("parent_component","child_component"):
            proof=row[side]["outer_source_provenance"]
            self.assertEqual(proof["status"],"serialized_outer_owner_match")
            self.assertTrue(proof["same_source_package"])
            self.assertEqual(proof["runtime_owner"],"not_established")

    def test_wrong_outer_generated_class_is_not_accepted(self):
        self.child[-1]["Outer"]["ObjectName"]="BlueprintGeneratedClass'Wrong_C'"
        self.save()
        graph,refs=self.report()
        proof=match_qualified(self.root,graph,refs)["records"][0]["child_component"]
        self.assertEqual(proof["status"],"outer_generated_class_mismatch")
        self.assertEqual(proof["outer_source_provenance"]["status"],"outer_generated_class_mismatch")

    def test_wrong_outer_package_is_not_accepted(self):
        self.child[-1]["Outer"]["ObjectPath"]="War/Content/Blueprints/Items/Parent.1"
        self.save()
        graph,refs=self.report()
        proof=match_qualified(self.root,graph,refs)["records"][0]["child_component"]
        self.assertEqual(proof["status"],"outer_generated_class_mismatch")
        self.assertFalse(proof["outer_source_provenance"]["same_source_package"])

    def test_missing_outer_reference_is_unresolved(self):
        self.child[-1].pop("Outer")
        self.save()
        graph,refs=self.report()
        self.assertEqual(match_qualified(self.root,graph,refs)["records"][0]["child_component"]["status"],
                         "outer_reference_missing")

    def test_source_hash_change_aborts(self):
        graph,refs=self.report()
        self.parent[-1]["Name"]="Modified"
        self.save()
        with self.assertRaisesRegex(ValueError,"hash"):
            match_qualified(self.root,graph,refs)

    def test_invalid_audit_digest_aborts(self):
        graph,refs=self.report()
        refs["relation_digest"]="not the same"
        with self.assertRaisesRegex(ValueError,"Unpinned"):
            match_qualified(self.root,graph,refs)


if __name__=="__main__":
    unittest.main()
