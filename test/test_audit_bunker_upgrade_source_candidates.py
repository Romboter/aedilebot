"""Synthetic evidence tests for saved upgrade CodeName source-only relationships."""
import unittest

from scripts.audit_bunker_upgrade_source_candidates import (
    inspect_declared_upgrade, prepare,
)


class UpgradeSourceCandidateTests(unittest.TestCase):
    def setUp(self):
        self.rows = {"PieceT1": {}, "PieceT2": {}, "OtherT2": {}}

    def test_no_serialized_upgrade_does_not_claim_no_runtime_upgrade(self):
        self.assertEqual(
            inspect_declared_upgrade({}, self.rows, [("Base", 1)], [("Base", 2)])["status"],
            "upgrade_not_serialized")

    def test_saved_none_sentinel_not_target(self):
        self.assertEqual(
            inspect_declared_upgrade({"UpgradeStructureCodeName": "None"},
                                     self.rows, [("Base", 1)], [("Base", 2)])["status"],
            "upgrade_saved_none_name_sentinel")

    def test_explicit_exact_next_tier_is_candidate_only(self):
        result = inspect_declared_upgrade(
            {"UpgradeStructureCodeName": "PieceT2"}, self.rows,
            [("Base", 1), ("Blank", 1)],
            [("Base", 2), ("Radar", 2)])
        self.assertEqual(result["status"], "exact_saved_target_with_reference_tier_step_candidates")
        self.assertEqual(result["same_reference_next_tier_candidates"],
                         [{"type": "Base", "from_tier": 1, "to_tier": 2}])
        self.assertEqual(result["runtime_upgrade_behavior"], "not_established")
        self.assertEqual(result["original_upgrade_property_type"], "not_inspected")

    def test_multiple_same_type_step_candidates_sorted_deterministically(self):
        result = inspect_declared_upgrade(
            {"UpgradeStructureCodeName": "PieceT2"}, self.rows,
            [("Radar", 1), ("Base", 1), ("Radar", 2), ("Base", 2)],
            [("Radar", 3), ("Base", 3), ("Base", 2), ("Radar", 2)])
        self.assertEqual(
            result["same_reference_next_tier_candidates"],
            [
                {"type": "Base", "from_tier": 1, "to_tier": 2},
                {"type": "Base", "from_tier": 2, "to_tier": 3},
                {"type": "Radar", "from_tier": 1, "to_tier": 2},
                {"type": "Radar", "from_tier": 2, "to_tier": 3},
            ])

    def test_cross_type_or_nonadjacent_tier_not_promoted(self):
        result = inspect_declared_upgrade(
            {"UpgradeStructureCodeName": "OtherT2"}, self.rows,
            [("Base", 1)], [("Other", 2), ("Base", 3)])
        self.assertEqual(result["status"], "exact_saved_target_without_reference_tier_step")
        self.assertEqual(result["same_reference_next_tier_candidates"], [])

    def test_missing_exact_row_is_not_fuzzily_resolved(self):
        result = inspect_declared_upgrade(
            {"UpgradeStructureCodeName": "piecet2"}, self.rows,
            [("Base", 1)], [("Base", 2)])
        self.assertEqual(result["status"], "upgrade_saved_target_not_in_original_structure_table")

    def test_nonstring_saved_target_is_unverified(self):
        result = inspect_declared_upgrade(
            {"UpgradeStructureCodeName": {"ObjectPath": "/Script/War.SomeClass"}},
            self.rows, [("Base", 1)], [("Base", 2)])
        self.assertEqual(result["status"], "upgrade_saved_non_name_scalar")
        self.assertEqual(result["shape"], "struct")

    def test_only_original_type_proven_row_links(self):
        proven = {"package": "Structures/Forts/A", "saved_default_export": "Default__A",
                  "row_identity": {"status": "original_nameproperty_and_fname_row",
                                   "row": "PieceT1"}}
        untyped = {"package": "Structures/Forts/B", "saved_default_export": "Default__B",
                   "row_identity": {"status": "saved_string_row_match_type_unverified",
                                    "row": "PieceT2"}}
        bench = [
            {"status": "unique_typed_source_row_candidate", "reference_type": "Base",
             "reference_tier": 1, "typed_match_rows": [{"row": "PieceT1"}]},
        ]
        typed, prof = prepare([proven, untyped], bench)
        self.assertEqual(set(typed), {"PieceT1"})
        self.assertEqual(prof["PieceT1"], [("Base", 1)])

    def test_fabricated_untyped_reference_row_rejected(self):
        with self.assertRaisesRegex(ValueError, "unverified"):
            prepare([], [
                {"status": "unique_typed_source_row_candidate",
                 "reference_type": "Base", "reference_tier": 1,
                 "typed_match_rows": [{"row": "PieceT1"}]}])

    def test_bad_tier_rejected(self):
        with self.assertRaisesRegex(ValueError, "tier"):
            prepare([], [
                {"status": "reference_tier_unavailable", "reference_type": "Base",
                 "reference_tier": 0, "typed_match_rows": []},
                {"status": "no_exact_numeric_row_candidate", "reference_type": "Base",
                 "reference_tier": 4, "typed_match_rows": []}])


if __name__ == "__main__":
    unittest.main()
