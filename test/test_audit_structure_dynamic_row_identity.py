"""Synthetic source-only typed structure dynamic row identity tests."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_structure_dynamic_row_identity import audit, parse_type_log
from scripts.index_blueprint_graph import build_index


TAGS = (
    "TABLE\tWar/Content/Blueprints/Data/BPStructureDynamicData\t"
    "BPStructureDynamicData\tFName\n"
    "TYPE\tWar/Content/Blueprints/Structures/Pillbox\t"
    "Default__Pillbox_C\tCodeName\tNameProperty\n"
)


class StructureDynamicRowIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("Data/BPAmmoDynamicData.json", [{"Name": "Ammo", "Rows": {}}])
        self.write("Data/BPMountDynamicData.json", [{"Name": "Mount", "Rows": {}}])
        self.write("Data/BPStructureDynamicData.json", [{
            "Name": "BPStructureDynamicData", "Rows": {
                "PillboxCode": {"MaxHealth": 1500, "RepairCost": 100,
                                "StructuralIntegrity": 0.97,
                                "DecayStartHours": 24, "DecayDurationHours": 36},
                "UnusedCode": {"MaxHealth": 100},
            }
        }])
        self.write("Structures/Pillbox.json", [
            {"Name": "Pillbox_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War.Buildable"}},
            {"Name": "Default__Pillbox_C", "Properties": {
                "CodeName": "PillboxCode", "Health": 1450, "ArmourType": "Tier1Structure",
            }},
        ])
        self.write("Structures/Bare.json", [
            {"Name": "Bare_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War.Buildable"}},
            {"Name": "Default__Bare_C", "Properties": {}},
        ])

    def write(self, name, value):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value), encoding="utf-8")

    def graph(self):
        return build_index(self.root, "26058282")

    def test_exact_typed_source_identity_not_runtime_use(self):
        r = audit(self.root, self.graph(), TAGS, "pinned-inspector-commit")
        c = r["coverage"]
        self.assertEqual(c["table_rows"], 2)
        self.assertEqual(c["saved_codename_records"], 1)
        self.assertEqual(c["status_counts"]["original_nameproperty_and_fname_row"], 1)
        self.assertEqual(c["status_counts"]["codename_not_serialized"], 1)
        self.assertEqual(c["distinct_matched_rows"], 1)
        self.assertFalse(r["safe_for_unattended_publication"])
        item = r["records"][0]
        self.assertEqual(item["row_identity"]["row"], "PillboxCode")
        self.assertEqual(item["saved_row_fields"]["StructuralIntegrity"]["shape"], "number")
        self.assertEqual(item["saved_class_fields"]["Health"]["status"], "explicit_saved")
        self.assertEqual(item["effective_runtime_row_values"], "not_established")
        self.assertNotEqual(item["saved_class_fields"]["Health"]["value_sha256"],
                            item["saved_row_fields"]["MaxHealth"]["value_sha256"])

    def test_string_equal_without_original_tag_not_promoted(self):
        r = audit(self.root, self.graph())
        self.assertEqual(r["coverage"]["status_counts"]["saved_string_row_match_type_unverified"], 1)
        self.assertEqual(r["coverage"]["table_key_type"], "not_inspected")

    def test_missing_row_not_fuzzily_matched(self):
        file = self.root / "Structures/Pillbox.json"
        text = file.read_text().replace("PillboxCode", "pillboxcode")
        file.write_text(text)
        r = audit(self.root, self.graph(), TAGS, "pinned-inspector-commit")
        self.assertEqual(r["coverage"]["status_counts"]["missing_exact_row"], 1)
        self.assertEqual(r["records"][0]["row_identity"]["case_only_candidates_unverified"], ["PillboxCode"])
        self.assertIsNone(r["records"][0]["row_identity"]["row"])

    def test_wrong_original_code_type_not_promoted(self):
        wrong = TAGS.replace("CodeName\tNameProperty", "CodeName\tStrProperty")
        r = audit(self.root, self.graph(), wrong, "pinned-inspector-commit")
        self.assertEqual(r["coverage"]["status_counts"]["saved_string_row_match_type_unverified"], 1)

    def test_inspector_requires_table_fname_proof(self):
        bad = TAGS.replace("BPStructureDynamicData\tFName", "BPStructureDynamicData\tFString")
        with self.assertRaisesRegex(ValueError, "row key type"):
            audit(self.root, self.graph(), bad, "pinned-inspector-commit")

    def test_changed_package_rejected(self):
        graph = self.graph()
        file = self.root / "Structures/Pillbox.json"
        file.write_text(file.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "hash"):
            audit(self.root, graph)

    def test_tampered_index_fingerprint_rejected(self):
        graph = self.graph()
        graph["declarations"].clear()
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            audit(self.root, graph)

    def test_tag_parser_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate table type tag"):
            parse_type_log(TAGS + TAGS)
        with self.assertRaisesRegex(ValueError, "Duplicate original CodeName tag"):
            parse_type_log(TAGS + TAGS.splitlines(keepends=True)[1])

    def test_type_log_without_inspector_pin_rejected(self):
        with self.assertRaisesRegex(ValueError, "pinned commit"):
            audit(self.root, self.graph(), TAGS)


if __name__ == "__main__":
    unittest.main()
