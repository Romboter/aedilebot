"""Synthetic source-only structure seat mount identity audit tests."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_structure_seat_mount_sources import audit
from scripts.index_blueprint_graph import build_index

SRC = "War/Content/Blueprints/"
class TestStructureSeatSources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {}}])
        self.write("Data/BPMountDynamicData.json", [{"Rows": {"PillboxGun": {"DamageMultiplier": 1.2}}}])
        self.write("Structures/BPPillbox.json", [
            {"Name": "BPPillbox_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War.Structure"}},
            {"Name": "Default__BPPillbox_C", "Properties": {}},
            {"Name": "SeatTemplate", "Type": "StructureSeatComponent",
             "Outer": {"ObjectName": "BlueprintGeneratedClass'BPPillbox_C'",
                       "ObjectPath": SRC + "Structures/BPPillbox.1"},
             "Properties": {
                 "MountCodeName": "PillboxGun",
                 "MountComponent": {
                     "ObjectName": "BlueprintGeneratedClass'BPGun_C'",
                     "ObjectPath": SRC + "Items/BPGun.99"},
             }},
        ])
        self.write("Items/BPGun.json", [
            {"Name": "BPGun_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War.Mount"}},
            {"Name": "Default__BPGun_C", "Properties": {"AmmoName": "TestAmmo"}},
        ])

    def write(self, name, val):
        p = self.root / name
        p.parent.mkdir(exist_ok=True,parents=True)
        p.write_text(json.dumps(val), encoding="utf-8")

    def change_seat(self, fn):
        p = self.root / "Structures/BPPillbox.json"
        value = json.loads(p.read_text())
        fn(value[2])
        self.write("Structures/BPPillbox.json", value)

    def test_verified_saved_owner_mount_generated_class_and_exact_row(self):
        out = audit(self.root, build_index(self.root, "26058282"))
        self.assertFalse(out["safe_for_unattended_publication"])
        self.assertEqual(out["coverage"]["structure_seat_component_exports"],1)
        rec = out["records"][0]
        self.assertEqual(rec["saved_outer_owner_status"], "saved_owner_class_and_outer_verified")
        self.assertEqual(rec["mount_code"]["status"], "exact_saved_row_present")
        self.assertEqual(rec["mount_component"]["status"], "unique_saved_generated_class")
        self.assertEqual(rec["mount_component"]["saved_default_matches"], 1)
        self.assertEqual(rec["effective_runtime_ammo"], "not_established")

    def test_missing_saved_fields_do_not_inherit(self):
        self.change_seat(lambda s: s["Properties"].clear())
        out = audit(self.root, build_index(self.root, "26058282"))
        self.assertEqual(out["records"][0]["mount_code"]["status"], "not_serialized")
        self.assertEqual(out["records"][0]["mount_component"]["status"], "not_serialized")

    def test_case_only_row_not_promoted(self):
        self.change_seat(lambda s: s["Properties"].update(MountCodeName="pillboxgun"))
        out = audit(self.root, build_index(self.root, "26058282"))
        code = out["records"][0]["mount_code"]
        self.assertEqual(code["status"], "row_missing")
        self.assertEqual(code["case_only_candidates_unverified"], ["PillboxGun"])

    def test_no_numeric_export_index_guess(self):
        self.change_seat(lambda s: s["Properties"]["MountComponent"].update(ObjectPath=SRC + "Items/BPGun.999999"))
        out = audit(self.root, build_index(self.root, "26058282"))
        self.assertEqual(out["records"][0]["mount_component"]["status"], "unique_saved_generated_class")

    def test_unsupported_class_name_not_guessed(self):
        self.change_seat(lambda s: s["Properties"]["MountComponent"].update(ObjectName="OtherClass'BPGun_C'"))
        out = audit(self.root, build_index(self.root, "26058282"))
        self.assertEqual(out["records"][0]["mount_component"]["status"], "unsupported_generated_class_object_name")

    def test_missing_export_unresolved(self):
        self.change_seat(lambda s: s["Properties"]["MountComponent"].update(ObjectPath=SRC + "Items/Absent.0"))
        out = audit(self.root, build_index(self.root, "26058282"))
        self.assertEqual(out["records"][0]["mount_component"]["status"], "target_package_not_exported")

    def test_false_owner_not_qualified(self):
        self.change_seat(lambda s: s["Outer"].update(ObjectName="BlueprintGeneratedClass'Unknown_C'"))
        out = audit(self.root, build_index(self.root, "26058282"))
        self.assertEqual(out["records"][0]["saved_outer_owner_status"], "outer_owner_unresolved")

    def test_source_sha_drift_fails_closed(self):
        graph = build_index(self.root, "26058282")
        p = self.root / "Structures/BPPillbox.json"
        p.write_text(p.read_text() + "\n")
        with self.assertRaisesRegex(ValueError,"hash"):
            audit(self.root, graph)

    def test_table_sha_drift_fails_closed(self):
        graph = build_index(self.root,"26058282")
        p = self.root / "Data/BPMountDynamicData.json"
        p.write_text(p.read_text()+"\n")
        with self.assertRaisesRegex(ValueError,"changed mount table"):
            audit(self.root,graph)

    def test_tampered_graph_fails_closed(self):
        graph = build_index(self.root,"26058282")
        graph["declarations"].append({"source": "Structures/BPPillbox", "record": "Default__BPPillbox_C", "field": "CodeName", "value": "Fake"})
        with self.assertRaisesRegex(ValueError,"fingerprint"):
            audit(self.root,graph)


if __name__ == "__main__":
    unittest.main()
