"""Test explicit inherited VehicleSeatComponent mount source edges, never CDO merge."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.index_blueprint_graph import build_index
from scripts.resolve_scs_component_keys import resolve
from scripts.audit_scs_template_exports import inspect as template_audit
from scripts.resolve_qualified_scs_template_exports import inspect as qualified_exports
from scripts.audit_inherited_seat_mount_sources import analyze


class SeatMountSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.table_rows = {"ParentGun": {"DamageMultiplier": 1.0},
                           "ChildGun": {"DamageMultiplier": 1.5},
                           "childgun": {"DamageMultiplier": 1.2}}
        self.write("Data/BPMountDynamicData.json", [{"Rows": self.table_rows}])
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {}}])
        self.write("Items/Gun.json", [
            {"Name": "Gun_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War"}}
        ])
        self.parent = [
            {"Name": "Parent_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "ParentSCS", "Type": "SCS_Node", "Properties": {
                "InternalVariableName": "SeatMount", "VariableGuid": "guid-1",
                "ComponentTemplate": {"ObjectPath": "War/Content/Blueprints/Vehicles/Parent.3",
                                      "ObjectName": "VehicleSeatComponent'Parent_C:Seat0'"},
            }},
            {"Name": "Seat0", "Type": "VehicleSeatComponent",
             "Outer": {"ObjectPath": "War/Content/Blueprints/Vehicles/Parent.1",
                       "ObjectName": "BlueprintGeneratedClass'Parent_C'"},
             "Properties": {
                 "MountCodeName": "ParentGun",
                 "MountComponent": {"ObjectPath": "War/Content/Blueprints/Items/Gun.1",
                                    "ObjectName": "BlueprintGeneratedClass'Gun_C'"},
             }},
        ]
        self.child = [
            {"Name": "Child_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Vehicles/Parent.1"}},
            {"Name": "Handler", "Type": "InheritableComponentHandler", "Properties": {
                "Records": [{
                    "ComponentKey": {
                        "OwnerClass": {"ObjectPath": "War/Content/Blueprints/Vehicles/Parent.1"},
                        "SCSVariableName": "SeatMount", "AssociatedGuid": "guid-1"},
                    "ComponentTemplate": {
                        "ObjectPath": "War/Content/Blueprints/Vehicles/Child.3",
                        "ObjectName": "VehicleSeatComponent'Child_C:SeatOverride'"},
                }]
            }},
            {"Name": "SeatOverride", "Type": "VehicleSeatComponent",
             "Outer": {"ObjectPath": "War/Content/Blueprints/Vehicles/Child.1",
                       "ObjectName": "BlueprintGeneratedClass'Child_C'"},
             "Properties": {
                 "MountCodeName": "ChildGun",
                 "MountComponent": {"ObjectPath": "War/Content/Blueprints/Items/Gun.1",
                                    "ObjectName": "BlueprintGeneratedClass'Gun_C'"},
             }},
        ]
        self.save()

    def write(self, relative, blob):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(blob), encoding="utf-8")

    def save(self):
        self.write("Vehicles/Parent.json", self.parent)
        self.write("Vehicles/Child.json", self.child)

    def inputs(self):
        graph = build_index(self.root, "26058282")
        base = resolve(self.root, graph)
        typed = {
            "source_build_id": graph["source_build_id"],
            "relation_digest": graph["relation_digest"],
            "status": "review_only_type_gated_scs_case_identity",
            "safe_for_unattended_publication": False,
            "reviewed_candidates": [],
        }
        refs = template_audit(self.root, graph, base, typed)
        identities = qualified_exports(self.root, graph, refs)
        return graph, identities

    def test_both_explicit_mount_names_join_exact_table_rows(self):
        graph, identities = self.inputs()
        result = analyze(self.root, graph, identities)
        self.assertEqual(result["coverage"]["counts"]["verified_seat_source_pairs"], 1)
        row = result["records"][0]
        self.assertEqual(row["parent_mount_code"]["status"], "row_present")
        self.assertEqual(row["child_mount_code"]["status"], "row_present")
        self.assertEqual(row["child_mount_code"]["saved_value"], "ChildGun")
        self.assertEqual(row["mount_code_comparison"], "both_serialized_changed")
        self.assertEqual(row["mount_component_comparison"], "both_serialized_same")
        self.assertEqual(row["child_mount_component"]["status"],
                         "explicit_blueprint_target_exported")
        self.assertEqual(row["child_mount_component"]["target_package"], "Items/Gun")
        self.assertEqual(row["child_mount_component"]["exact_target_export"], "not_established")
        self.assertEqual(row["effective_runtime_mount"], "not_established")
        self.assertEqual(row["effective_runtime_ammo"], "not_established")
        self.assertFalse(result["safe_for_unattended_publication"])

    def test_parent_only_does_not_fill_child(self):
        self.child[-1]["Properties"].clear()
        self.save()
        graph, identities = self.inputs()
        row = analyze(self.root, graph, identities)["records"][0]
        self.assertEqual(row["mount_code_comparison"], "parent_only_serialized")
        self.assertEqual(row["mount_component_comparison"], "parent_only_serialized")
        self.assertEqual(row["child_mount_code"]["status"], "not_serialized")
        self.assertEqual(row["child_mount_component"]["status"], "not_serialized")
        self.assertNotIn("saved_value", row["child_mount_code"])

    def test_saved_none_fails_closed_as_unset(self):
        self.child[-1]["Properties"]["MountCodeName"] = "None"
        self.save()
        graph, identities = self.inputs()
        row = analyze(self.root, graph, identities)["records"][0]
        self.assertEqual(row["child_mount_code"]["status"], "none_sentinel_candidate")
        self.assertFalse(row["child_mount_code"]["exact_row_identity_from_saved_field"])
        self.assertEqual(row["child_mount_code"]["effective_mount_name"], "not_established")

    def test_explicit_null_component_is_not_inherited(self):
        self.child[-1]["Properties"]["MountComponent"] = None
        self.save()
        graph, identities = self.inputs()
        row = analyze(self.root, graph, identities)["records"][0]
        self.assertEqual(row["child_mount_component"]["status"], "explicit_null")
        self.assertEqual(row["mount_component_comparison"], "both_serialized_changed")

    def test_missing_row_reports_only_case_candidates(self):
        self.child[-1]["Properties"]["MountCodeName"] = "CHILDGUN"
        self.save()
        graph, identities = self.inputs()
        row = analyze(self.root, graph, identities)["records"][0]
        entry = row["child_mount_code"]
        self.assertEqual(entry["status"], "row_missing")
        self.assertEqual(entry["case_only_row_candidates_unverified"], ["ChildGun", "childgun"])
        self.assertFalse(entry["exact_row_identity_from_saved_field"])

    def test_child_only_field_remains_explicit(self):
        self.parent[-1]["Properties"].clear()
        self.save()
        graph, identities = self.inputs()
        row = analyze(self.root, graph, identities)["records"][0]
        self.assertEqual(row["mount_code_comparison"], "child_only_serialized")
        self.assertEqual(row["mount_component_comparison"], "child_only_serialized")

    def test_modified_data_table_hash_is_rejected(self):
        graph, identities = self.inputs()
        self.table_rows["Changed"] = {"DamageMultiplier": 5}
        self.write("Data/BPMountDynamicData.json", [{"Rows": self.table_rows}])
        with self.assertRaisesRegex(ValueError, "DataTable"):
            analyze(self.root, graph, identities)

    def test_modified_seat_hash_rejected(self):
        graph, identities = self.inputs()
        self.child[-1]["Properties"]["MountCodeName"] = "ParentGun"
        self.save()
        with self.assertRaisesRegex(ValueError, "hash"):
            analyze(self.root, graph, identities)

    def test_mismatched_index_edge_cannot_be_accepted(self):
        graph, identities = self.inputs()
        edge = next(e for e in graph["numeric_row_references"]
                    if e["source"] == "Vehicles/Child" and e["field"] == "MountCodeName")
        edge["row"] = "ParentGun"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            analyze(self.root, graph, identities)

    def test_invalid_source_component_owner_refused(self):
        graph, identities = self.inputs()
        identities["records"][0]["child_component"]["outer_source_provenance"]["status"] = "unverified"
        with self.assertRaisesRegex(ValueError, "Unverified"):
            analyze(self.root, graph, identities)

    def test_guid_mismatch_is_never_patched_through(self):
        self.child[1]["Properties"]["Records"][0]["ComponentKey"]["AssociatedGuid"] = "bad-guid"
        self.save()
        graph, identities = self.inputs()
        self.assertEqual(identities["coverage"]["source_pairs"], 0)
        self.assertEqual(analyze(self.root, graph, identities)["coverage"]["counts"].get(
            "verified_seat_source_pairs", 0), 0)


if __name__ == "__main__":
    unittest.main()
