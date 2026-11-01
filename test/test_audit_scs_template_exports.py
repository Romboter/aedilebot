"""Regression fixtures for source-only parent/child SCS template export survey."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.index_blueprint_graph import build_index
from scripts.resolve_scs_component_keys import resolve
from scripts.audit_scs_template_exports import inspect


class TemplateExportAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.write("Data/BPAmmoDynamicData.json", [{"Rows":{}}])
        self.write("Data/BPMountDynamicData.json", [{"Rows":{}}])
        self.parent=[
            {"Name":"Parent_C","Type":"BlueprintGeneratedClass","SuperStruct":{"ObjectPath":"/Script/War"}},
            {"Name":"SCS_Node_1","Type":"SCS_Node","Properties":{
                "InternalVariableName":"Cannon","VariableGuid":"GUID-1",
                "ComponentTemplate":{"ObjectPath":"War/Content/Blueprints/Items/Parent.3",
                                     "ObjectName":"ParentTemplate"}}},
            {"Name":"ParentTemplate","Type":"StaticMeshComponent","Properties":{"Dummy":"safe"}},
        ]
        self.child=[
            {"Name":"Child_C","Type":"BlueprintGeneratedClass",
             "SuperStruct":{"ObjectPath":"War/Content/Blueprints/Items/Parent.1"}},
            {"Name":"Handler","Type":"InheritableComponentHandler","Properties":{"Records":[{
                "ComponentKey":{
                    "OwnerClass":{"ObjectPath":"War/Content/Blueprints/Items/Parent.1"},
                    "SCSVariableName":"Cannon","AssociatedGuid":"GUID-1"},
                "ComponentTemplate":{"ObjectPath":"War/Content/Blueprints/Items/Child.3",
                                     "ObjectName":"ChildTemplate"}}]}},
            {"Name":"ChildTemplate","Type":"StaticMeshComponent","Properties":{"Dummy":"safe"}},
        ]
        self.save()

    def write(self,path,object_value):
        file=self.root/path
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(object_value),encoding="utf-8")

    def save(self):
        self.write("Items/Parent.json",self.parent)
        self.write("Items/Child.json",self.child)

    def inputs(self):
        graph=build_index(self.root,"26058282")
        matcher=resolve(self.root,graph)
        typed={"source_build_id":graph["source_build_id"],
               "relation_digest":graph["relation_digest"],
               "status":"review_only_type_gated_scs_case_identity",
               "safe_for_unattended_publication":False,
               "reviewed_candidates":[]}
        return graph,matcher,typed

    def test_explicit_export_names_found_in_both_source_packages(self):
        g,m,t=self.inputs()
        r=inspect(self.root,g,m,t)
        self.assertEqual(r["coverage"]["counts"]["source_components_checked"],1)
        row=r["records"][0]
        self.assertEqual(row["parent_template_reference"]["status"],"object_name_exact_export")
        self.assertEqual(row["child_template_reference"]["status"],"object_name_exact_export")
        self.assertEqual(row["parent_scs_node"],"SCS_Node_1")
        self.assertEqual(row["effective_runtime_component"],"not_established")
        self.assertFalse(r["safe_for_unattended_publication"])

    def test_child_object_name_does_not_guess_suffix(self):
        self.child[-1]["Name"]="DifferentExport"
        self.save()
        g,m,t=self.inputs()
        row=inspect(self.root,g,m,t)["records"][0]
        self.assertEqual(row["child_template_reference"]["status"],"object_name_not_export_name")

    def test_missing_child_objectname_is_reported_not_synthesized(self):
        del self.child[1]["Properties"]["Records"][0]["ComponentTemplate"]["ObjectName"]
        self.save()
        g,m,t=self.inputs()
        row=inspect(self.root,g,m,t)["records"][0]
        self.assertEqual(row["child_template_reference"]["status"],"missing_object_name")

    def test_parent_duplicate_template_export_name_is_ambiguous(self):
        self.parent.append({"Name":"ParentTemplate","Type":"StaticMeshComponent","Properties":{}})
        self.save()
        g,m,t=self.inputs()
        row=inspect(self.root,g,m,t)["records"][0]
        self.assertEqual(row["parent_template_reference"]["status"],"object_name_ambiguous")

    def test_tampered_graph_changes_source_and_aborts(self):
        g,m,t=self.inputs()
        self.parent[-1]["Properties"]["Dummy"]="changed"
        self.save()
        with self.assertRaisesRegex(ValueError,"hash"):
            inspect(self.root,g,m,t)

    def test_invalid_typed_build_aborts(self):
        g,m,t=self.inputs()
        t["source_build_id"]="modified"
        with self.assertRaisesRegex(ValueError,"Unpinned"):
            inspect(self.root,g,m,t)

    def test_wrong_template_target_package_cannot_cross_join(self):
        self.child[1]["Properties"]["Records"][0]["ComponentTemplate"]={
            "ObjectPath":"War/Content/Blueprints/Items/Parent.3",
            "ObjectName":"ParentTemplate"}
        self.save()
        g,m,t=self.inputs()
        row=inspect(self.root,g,m,t)["records"][0]
        self.assertEqual(row["child_template_reference"]["status"],"target_package_mismatch")


if __name__=="__main__":
    unittest.main()
