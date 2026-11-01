"""Synthetic coverage for FoxBunker source-only numeric row candidates."""
import hashlib
import json
import unittest

from scripts.audit_foxbunker_structure_row_benchmark import (
    PUBLIC_REFERENCE_SHA256, VALIDATED_BOT_ALIASES, collect_numeric_rows,
    compare, number, reference_table,
)


def reference_fixture():
    names = list(VALIDATED_BOT_ALIASES) + [
        "Corner", "Fire Station", "Hearth", "Foundation", "Radar"]
    assert len(names) == 22
    defs = []
    for i, name in enumerate(names):
        defs.append([name, f"X{i}", 1,
                     [[0.97, 2000, 75, 75, 75, 0]] * 3])
    return ("const unrelated = [1, 2];\nconst STRUCTURES = " +
            json.dumps(defs) + ";\n// More public JavaScript.\n").encode()


class ReferenceParsing(unittest.TestCase):
    def test_expected_reference_fingerprint_is_fixed(self):
        self.assertEqual(len(PUBLIC_REFERENCE_SHA256), 64)

    def test_json_literal_not_executed(self):
        blob = reference_fixture()
        parsed = reference_table(blob, hashlib.sha256(blob).hexdigest())
        self.assertEqual(len(parsed), 22)
        self.assertEqual(parsed[0]["name"], "Base")
        self.assertEqual(parsed[0]["tiers"][0][:3],
                         (number(0.97), number(2000), number(75)))

    def test_wrong_fingerprint_rejected(self):
        with self.assertRaisesRegex(ValueError, "changed"):
            reference_table(reference_fixture())

    def test_missing_tier_at_or_above_minimum_rejected(self):
        blob = reference_fixture().replace(b'[0.97, 2000, 75, 75, 75, 0]', b'null', 1)
        # JSON null replaces first T1 tuple of a min-T1 piece.
        with self.assertRaisesRegex(ValueError, "Missing tier"):
            reference_table(blob, hashlib.sha256(blob).hexdigest())

    def test_malformed_or_missing_ref_rejected(self):
        blob = b"const STRUCTURES = Array.from({length:22});"
        with self.assertRaisesRegex(ValueError, "Missing exact"):
            reference_table(blob, hashlib.sha256(blob).hexdigest())


class CandidateMatching(unittest.TestCase):
    def setUp(self):
        self.ref = reference_table(reference_fixture(), hashlib.sha256(reference_fixture()).hexdigest())

    def test_numeric_does_not_coerce_bool_or_string(self):
        self.assertIsNone(number(True))
        self.assertIsNone(number("2000"))
        self.assertEqual(number(1), number(1.0))

    def test_exact_triplet_not_partial_matches(self):
        rows, skipped = collect_numeric_rows({
            "A": {"StructuralIntegrity": .97, "MaxHealth": 2000, "RepairCost": 75},
            "B": {"StructuralIntegrity": .97, "MaxHealth": 2000, "RepairCost": 76},
            "C": {"StructuralIntegrity": .97, "MaxHealth": 2000, "RepairCost": "75"},
        })
        self.assertEqual(set(rows), {"A", "B"})
        self.assertEqual(skipped["missing_or_non_numeric_matched_fields"], 1)
        result = compare(self.ref, rows, [])
        self.assertEqual(result[0]["numeric_match_rows"], ["A"])
        self.assertEqual(result[0]["status"], "unattributed_numeric_row_candidates")

    def test_only_proven_typed_class_joins_count(self):
        rows = {"A": (number(.97), number(2000), number(75)),
                "B": (number(.97), number(2000), number(75))}
        rec = [
            {"row_identity": {"status": "original_nameproperty_and_fname_row",
                              "table": "Data/BPStructureDynamicData", "row": "A"},
             "package": "Structures/Fort/BA",
             "saved_default_export": "Default__BA_C", "source_sha256": "hash"},
            {"row_identity": {"status": "saved_string_row_match_type_unverified",
                              "table": "Data/BPStructureDynamicData", "row": "B"},
             "package": "Structures/Fort/BB",
             "saved_default_export": "Default__BB_C", "source_sha256": "hash"},
        ]
        result = compare(self.ref, rows, rec)
        self.assertEqual(result[0]["status"], "unique_typed_source_row_candidate")
        self.assertEqual(result[0]["numeric_match_rows"], ["A", "B"])
        self.assertEqual([r["row"] for r in result[0]["typed_match_rows"]], ["A"])

    def test_different_distinct_typed_rows_remain_ambiguous(self):
        rows = {k: (number(.97), number(2000), number(75)) for k in ("A", "B")}
        rec = [
            {"row_identity": {"status": "original_nameproperty_and_fname_row",
                              "table": "Data/BPStructureDynamicData", "row": k},
             "package": "Structures/Fort/B"+k,
             "saved_default_export": "Default__B"+k, "source_sha256": "hash"}
            for k in ("A", "B")]
        result = compare(self.ref, rows, rec)
        self.assertEqual(result[0]["status"], "ambiguous_typed_source_row_candidates")
        self.assertEqual(len(result[0]["typed_match_rows"]), 2)

    def test_unknown_rows_are_not_invented(self):
        result = compare(self.ref, {}, [])
        self.assertEqual(result[0]["status"], "no_exact_numeric_row_candidate")
        self.assertEqual(result[0]["typed_match_rows"], [])

    def test_unavailable_tier_has_no_matching(self):
        ref = [dict(self.ref[0])]
        ref[0]["tiers"] = [None, self.ref[0]["tiers"][1], self.ref[0]["tiers"][2]]
        result = compare(ref, {}, [])
        self.assertEqual(result[0]["status"], "reference_tier_unavailable")
        self.assertEqual(result[0]["numeric_match_rows"], [])

    def test_typed_row_wrong_table_rejected(self):
        rows = {"A": (number(.97), number(2000), number(75))}
        with self.assertRaisesRegex(ValueError, "Unexpected typed identity table"):
            compare(self.ref, rows, [{
                "row_identity": {"status": "original_nameproperty_and_fname_row",
                                 "row": "A", "table": "Data/BPMountDynamicData"},
                "package": "Structures/Fort/BA", "saved_default_export": "Default__BA",
                "source_sha256": "h"}])


if __name__ == "__main__":
    unittest.main()
