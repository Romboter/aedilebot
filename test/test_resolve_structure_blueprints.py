"""Synthetic structure identity checks; no proprietary game files."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.resolve_structure_blueprints import resolve_structure


class StructureIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write("Data/BPStructureDynamicData.json", [{"Rows": {
            "WatchTower": {"MaxHealth": 350},
            "RailTrackSplineFoundation": {"MaxHealth": 500},
            "DecoySameHP": {"MaxHealth": 350},
        }}])
        self.write("Structures/BPWatchTower.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "BPWatchTower_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__BPWatchTower_C", "Properties": {
                "CodeName": "WatchTower", "MaxHealth": 350}},
        ])

    def write(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data), encoding="utf-8")

    def test_native_armour_is_unresolved_not_assumed_no_armour(self):
        out = resolve_structure(self.root, Path("Structures/BPWatchTower.json"), "26058282")
        self.assertEqual(out["health"]["status"], "named_dynamic_row_resolved")
        self.assertEqual(out["health"]["max_health"], 350)
        self.assertEqual(out["armour"]["status"], "unresolved")
        self.assertIn("not present", out["armour"]["reason"].replace("_", " "))
        self.assertFalse(out["safe_for_unattended_publication"])

    def test_inherited_armour_and_codename_keep_parent_path(self):
        self.write("Structures/Base.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Base_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Base_C", "Properties": {
                "CodeName": "RailTrackSplineFoundation",
                "ArmourType": "EArmourType::Tier3BStructure", "MaxHealth": 500}},
        ])
        self.write("Structures/Child.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Child_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Structures/Base.1"}},
            {"Name": "Default__Child_C", "Properties": {"DisplayName": "Custom"}},
        ])
        out = resolve_structure(self.root, Path("Structures/Child.json"), "26058282")
        self.assertEqual(out["code_name"], "RailTrackSplineFoundation")
        self.assertEqual(out["armour"]["value"], "EArmourType::Tier3BStructure")
        self.assertEqual(out["health"]["max_health"], 500)
        self.assertTrue(any(x["role"] == "armour_identity" and x["asset"] == "Structures/Base.json"
                            for x in out["evidence"]))

    def test_blueprint_and_dynamic_health_mismatch_flags_review(self):
        self.write("Structures/BPWatchTower.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "BPWatchTower_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__BPWatchTower_C", "Properties": {
                "CodeName": "WatchTower", "MaxHealth": 420}},
        ])
        out = resolve_structure(self.root, Path("Structures/BPWatchTower.json"), "26058282")
        self.assertEqual(out["health"]["reason"], "blueprint_and_dynamic_table_health_disagree")

    def test_matching_health_is_not_identity_proof(self):
        self.write("Structures/BPWatchTower.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "BPWatchTower_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__BPWatchTower_C", "Properties": {
                "CodeName": "Unrelated", "MaxHealth": 350}},
        ])
        out = resolve_structure(self.root, Path("Structures/BPWatchTower.json"), "26058282")
        self.assertEqual(out["health"]["reason"], "named_structure_dynamic_row_missing")

    def test_missing_codename_is_unresolved_even_if_hp_matches(self):
        self.write("Structures/BPWatchTower.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "BPWatchTower_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__BPWatchTower_C", "Properties": {"MaxHealth": 350}},
        ])
        out = resolve_structure(self.root, Path("Structures/BPWatchTower.json"), "26058282")
        self.assertEqual(out["health"]["reason"], "structure_codename_missing")


if __name__ == "__main__":
    unittest.main()
