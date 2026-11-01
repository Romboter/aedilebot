"""Synthetic tests for source-only profile evidence and cautious candidate matching."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_nixie_damage_profile_sources import (
    audit, compare_profiles, damage_type_references, key_matches, table_rows,
)


class ProfileAuditTests(unittest.TestCase):
    def test_all_comparison_outcomes_and_missing(self):
        src = {
            "EDamageType::Explosive": {
                "Tier1Structure": 0.75, "Tier2Structure": 0.40,
                "Tier3Structure": 0.50, "Other": 0.90,
            },
            "AnotherDamageType": {"Tier1Structure": 0.30},
            "Missing": {"Tier1Structure": 0.1},
        }
        human = {"Explosive": {"Tier1Structure": "0.75", "Tier2Structure": "0.60",
                              "Tier3Structure": "0.50", "Other": "0.20"},
                 "Another": {"Tier1Structure": "0.60"}, "Orphan": {}}
        res = compare_profiles(src, human)
        counts = res["counts"]
        self.assertEqual(counts["direct_only"], 1)
        self.assertEqual(counts["complement_only"], 1)
        self.assertEqual(counts["both"], 1)
        self.assertEqual(counts["neither"], 2)
        self.assertEqual(counts["human_rows_unmatched"], 1)
        self.assertEqual(counts["alias_unique"], 2)
        self.assertEqual(counts["missing_human"], 1)

    def test_alias_collision_never_picks_arbitrary_row(self):
        src = {"EDamageType::Blast": {"Tier1Structure": 0.2}}
        human = {"Blast": {}, "BlastDamageType": {}}
        keys = key_matches(src, human)
        self.assertEqual(keys, [("EDamageType::Blast", None, "alias_ambiguous")])

    def test_saved_ammo_references_are_candidates_only(self):
        refs, counts = damage_type_references(
            {"Shell": {"DamageType": {"ObjectPath": "War/Content/Blueprints/DamageTypes/Explosive.Explosive_C"}},
             "Blank": {}, "Broken": {"DamageType": {"ObjectPath": "War/Content/Blueprints/DamageTypes/Absent.Absent_C"}}},
            {"DamageTypes/Explosive": ["Explosive_C"]},
        )
        self.assertEqual(counts["saved_reference_exported"], 1)
        self.assertEqual(counts["saved_reference_missing_export"], 1)
        self.assertEqual(counts["unresolved_reference"], 1)
        self.assertEqual(len(refs), 3)

    def test_exact_table_validation_and_end_to_end_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "Data"
            data.mkdir()
            (data / "DTDamageProfiles.json").write_text(json.dumps(
                [{"Name": "DTDamageProfiles", "Type": "DataTable", "Rows":
                  {"Explosive": {"Tier1Structure": 0.75}}}]), encoding="utf-8")
            (data / "BPAmmoDynamicData.json").write_text(json.dumps(
                [{"Name": "BPAmmoDynamicData", "Type": "DataTable", "Rows": {"Shell": {
                    "Damage": 100, "DamageType": {
                        "ObjectPath": "War/Content/Blueprints/DamageTypes/Explosive.Explosive_C"}}}}]), encoding="utf-8")
            dt = root / "DamageTypes"
            dt.mkdir()
            (dt / "Explosive.json").write_text(json.dumps(
                [{"Type": "BlueprintGeneratedClass", "Name": "Explosive_C"}]), encoding="utf-8")
            human = root / "Damage.json"
            human.write_text(json.dumps({"Explosive": {"Tier1Structure": "0.75"}}), encoding="utf-8")
            result = audit(root, human, "26058282")
            self.assertEqual(result["coverage"]["ammo_row_count"], 1)
            self.assertEqual(result["comparison"]["counts"]["direct_only"], 1)
            self.assertEqual(result["coverage"]["ammo_reference_status_counts"]["saved_reference_exported"], 1)
            self.assertFalse(result["safe_for_unattended_publication"])
            self.assertEqual(len(table_rows(data / "DTDamageProfiles.json")), 1)


if __name__ == "__main__":
    unittest.main()
