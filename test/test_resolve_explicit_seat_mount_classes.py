"""Synthetic source target-class proof for explicit VehicleSeatComponent MountComponent links."""
import json
import unittest

import test_audit_inherited_seat_mount_sources as fixtures
from scripts.audit_inherited_seat_mount_sources import analyze as seat_audit
from scripts.resolve_explicit_seat_mount_classes import resolve as class_resolve


class ExplicitMountTargetTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SeatMountSourceTests(
            "test_both_explicit_mount_names_join_exact_table_rows")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def result(self):
        graph, identities = self.fixture.inputs()
        seats = seat_audit(self.fixture.root, graph, identities)
        return graph, seats, class_resolve(self.fixture.root, graph, seats)

    def test_both_saved_mount_references_resolve_exact_source_class(self):
        graph, seats, report = self.result()
        self.assertEqual(report["coverage"]["counts"], {
            "child_unique_saved_generated_class_export": 1,
            "parent_unique_saved_generated_class_export": 1,
            "source_pairs_checked": 1,
        })
        result = report["records"][0]
        self.assertEqual(result["parent_mount_target"]["saved_generated_class"], "Gun_C")
        self.assertEqual(result["child_mount_target"]["target_package"], "Items/Gun")
        self.assertEqual(result["child_mount_target"]["generated_class_matches"], 1)
        self.assertEqual(result["child_mount_target"]["exact_saved_default_matches"], 0)
        self.assertEqual(result["child_mount_target"]["selected_runtime_cdo"], "not_established")
        self.assertEqual(result["effective_runtime_ammo"], "not_established")
        self.assertFalse(report["safe_for_unattended_publication"])

    def test_missing_child_source_reference_not_inherited(self):
        self.fixture.child[-1]["Properties"].pop("MountComponent")
        self.fixture.save()
        _, _, report = self.result()
        child = report["records"][0]["child_mount_target"]
        self.assertEqual(child["status"], "not_explicit_exported_mount_reference")
        self.assertEqual(child["source_status"], "not_serialized")
        self.assertEqual(child["runtime_mount"], "not_established")

    def test_generated_class_name_wrong_spelling_unresolved(self):
        self.fixture.child[-1]["Properties"]["MountComponent"]["ObjectName"] = (
            "BlueprintGeneratedClass'gun_C'")
        self.fixture.save()
        _, _, report = self.result()
        self.assertEqual(report["records"][0]["child_mount_target"]["status"],
                         "generated_class_not_exported")

    def test_unsupported_class_qualified_name_does_not_resolve(self):
        self.fixture.child[-1]["Properties"]["MountComponent"]["ObjectName"] = "Gun_C"
        self.fixture.save()
        _, _, report = self.result()
        self.assertEqual(report["records"][0]["child_mount_target"]["status"],
                         "unsupported_class_object_name")

    def test_duplicate_generated_class_export_is_unresolved(self):
        path = self.fixture.root / "Items/Gun.json"
        data = json.loads(path.read_text())
        data.append(dict(data[0]))
        self.fixture.write("Items/Gun.json", data)
        _, _, report = self.result()
        self.assertEqual(report["records"][0]["child_mount_target"]["status"],
                         "ambiguous_generated_class_export")

    def test_missing_target_export_is_not_guessed(self):
        (self.fixture.root / "Items/Gun.json").unlink()
        _, _, report = self.result()
        self.assertEqual(report["records"][0]["child_mount_target"]["status"],
                         "not_explicit_exported_mount_reference")
        self.assertEqual(report["records"][0]["child_mount_target"]["source_status"],
                         "explicit_blueprint_target_missing_export")

    def test_target_file_changed_after_index_rejected(self):
        graph, identities = self.fixture.inputs()
        seats = seat_audit(self.fixture.root, graph, identities)
        path = self.fixture.root / "Items/Gun.json"
        path.write_text(path.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "hash"):
            class_resolve(self.fixture.root, graph, seats)

    def test_saved_seat_reference_changed_after_index_rejected(self):
        graph, identities = self.fixture.inputs()
        seats = seat_audit(self.fixture.root, graph, identities)
        self.fixture.child[-1]["Properties"]["MountComponent"]["ObjectName"] = (
            "BlueprintGeneratedClass'Wrong_C'")
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, "hash"):
            class_resolve(self.fixture.root, graph, seats)

    def test_forged_report_path_rejected(self):
        graph, identities = self.fixture.inputs()
        seats = seat_audit(self.fixture.root, graph, identities)
        seats["records"][0]["child_mount_component"]["saved_object_path"] = (
            "War/Content/Blueprints/Items/Other.0")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            class_resolve(self.fixture.root, graph, seats)

    def test_invalid_qualified_source_digest_rejected(self):
        graph, identities = self.fixture.inputs()
        seats = seat_audit(self.fixture.root, graph, identities)
        seats["relation_digest"] = "wrong"
        with self.assertRaisesRegex(ValueError, "Unpinned"):
            class_resolve(self.fixture.root, graph, seats)


if __name__ == "__main__":
    unittest.main()
