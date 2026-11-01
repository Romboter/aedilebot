"""Source-only saved ammo field audit tests; no runtime CDO merge or damage."""
import json
import unittest

import test_audit_inherited_seat_mount_sources as fixtures
from scripts.audit_inherited_seat_mount_sources import analyze as seat_audit
from scripts.resolve_explicit_seat_mount_classes import resolve as mount_classes
from scripts.audit_mount_class_saved_ammo import audit


class SavedMountAmmoTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixtures.SeatMountSourceTests(
            "test_both_explicit_mount_names_join_exact_table_rows")
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.target = [
            {"Name": "Gun_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Gun_C", "Properties": {}},
        ]
        self.save()

    def save(self):
        self.fx.write("Items/Gun.json", self.target)

    def inputs(self):
        graph, identities = self.fx.inputs()
        seats = seat_audit(self.fx.root, graph, identities)
        classes = mount_classes(self.fx.root, graph, seats)
        return graph, classes

    def report(self):
        graph, classes = self.inputs()
        return audit(self.fx.root, graph, classes)

    def test_unsaved_fields_remain_unsaved_on_parent_and_child_mounts(self):
        result = self.report()
        self.assertEqual(result["coverage"]["counts"]["parent_verified_saved_class_defaults"], 1)
        self.assertEqual(result["coverage"]["counts"]["child_verified_saved_class_defaults"], 1)
        self.assertEqual(result["coverage"]["distinct_verified_mount_class_exports"], 1)
        self.assertEqual(len(result["records"]), 2)
        for entry in result["records"]:
            self.assertEqual(entry["saved_fields"]["AmmoName"]["status"], "not_serialized")
            self.assertEqual(entry["saved_fields"]["MultiAmmo"]["status"], "not_serialized")
            self.assertEqual(entry["effective_runtime_ammo"], "not_established")
        self.assertFalse(result["safe_for_unattended_publication"])

    def test_saved_ammo_name_does_not_become_runtime_selection(self):
        self.target[1]["Properties"]["AmmoName"] = "TestRound"
        self.save()
        result = self.report()
        self.assertEqual(result["records"][0]["saved_fields"]["AmmoName"]["saved_name"], "TestRound")
        self.assertEqual(result["records"][0]["saved_fields"]["AmmoName"]["status"], "explicit_saved_name")
        self.assertEqual(result["records"][0]["effective_runtime_ammo"], "not_established")

    def test_partial_multi_ammo_struct_never_gets_inferred_list(self):
        self.target[1]["Properties"]["MultiAmmo"] = {"AmmoSlotFilterAmounts": [1]}
        self.save()
        result = self.report()
        field = result["records"][0]["saved_fields"]["MultiAmmo"]
        self.assertEqual(field["status"], "saved_struct_without_names_array")
        self.assertEqual(field["saved_struct_fields"], ["AmmoSlotFilterAmounts"])
        self.assertNotIn("saved_names", field)

    def test_empty_array_is_distinct_from_unserialized_array(self):
        self.target[1]["Properties"]["MultiAmmo"] = {"CompatibleAmmoNames": []}
        self.save()
        field = self.report()["records"][0]["saved_fields"]["MultiAmmo"]
        self.assertEqual(field["status"], "explicit_empty_saved_names_array")
        self.assertEqual(field["saved_names"], [])

    def test_multiple_saved_options_are_source_evidence_only(self):
        self.target[1]["Properties"]["MultiAmmo"] = {
            "CompatibleAmmoNames": ["TestRoundA", "TestRoundB"],
            "AmmoSlotFilterAmounts": [0, 1]}
        self.save()
        field = self.report()["records"][0]["saved_fields"]["MultiAmmo"]
        self.assertEqual(field["status"], "explicit_saved_names_array")
        self.assertEqual(field["saved_names"], ["TestRoundA", "TestRoundB"])

    def test_saved_none_name_is_unset_candidate(self):
        self.target[1]["Properties"]["AmmoName"] = "None"
        self.save()
        self.assertEqual(self.report()["records"][0]["saved_fields"]["AmmoName"]["status"],
                         "saved_none_sentinel_candidate")

    def test_saved_parent_link_is_candidate_not_merged_fields(self):
        self.target[0]["SuperStruct"] = {
            "ObjectPath": "War/Content/Blueprints/Items/GunBase.1"}
        self.save()
        result = self.report()
        self.assertEqual(result["records"][0]["parent_blueprint_source_candidate"], "Items/GunBase")
        self.assertEqual(result["records"][0]["saved_fields"]["AmmoName"]["status"], "not_serialized")
        self.assertEqual(result["records"][0]["effective_runtime_mount"], "not_established")

    def test_changed_target_source_sha_fails_closed(self):
        graph, classes = self.inputs()
        self.target[1]["Properties"]["AmmoName"] = "Changed"
        self.save()
        with self.assertRaisesRegex(ValueError, "hash"):
            audit(self.fx.root, graph, classes)

    def test_forged_default_export_identity_rejected(self):
        graph, classes = self.inputs()
        classes["records"][0]["parent_mount_target"]["exact_saved_default_name"] = "OtherDefault"
        with self.assertRaisesRegex(ValueError, "diverged"):
            audit(self.fx.root, graph, classes)

    def test_missing_default_is_not_assumed_to_exist(self):
        self.target.pop()
        self.save()
        result = self.report()
        self.assertEqual(result["coverage"]["counts"]["parent_class_default_missing_or_ambiguous"], 1)
        self.assertEqual(result["coverage"]["counts"]["child_class_default_missing_or_ambiguous"], 1)
        self.assertEqual(result["records"], [])

    def test_missing_child_mount_reference_not_filled_from_parent(self):
        self.fx.child[-1]["Properties"].pop("MountComponent")
        self.fx.save()
        result = self.report()
        self.assertEqual(result["coverage"]["counts"]["child_not_explicit_class"], 1)
        self.assertEqual(result["coverage"]["counts"]["parent_verified_saved_class_defaults"], 1)


if __name__ == "__main__":
    unittest.main()
