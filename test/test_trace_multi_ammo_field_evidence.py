"""Fail-closed synthetic source evidence tests; not UE4.24 runtime CDO fixtures."""
import copy
import unittest

from scripts.trace_multi_ammo_field_evidence import collect_nested_field_evidence


class MultiAmmoFieldEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.properties = {
            "Child": {"MultiAmmo": {"AmmoSlotFilterAmounts": [2, 3]}},
            "Parent": {"MultiAmmo": {"CompatibleAmmoNames": ["LightTankAmmo"],
                                      "AmmoSlotFilterAmounts": [1]}},
            "Grandparent": {"MultiAmmo": {"CompatibleAmmoNames": ["MGAmmo"]}},
        }
        self.chain = [
            {"package": name, "sha256": "hash-" + name}
            for name in ("Child", "Parent", "Grandparent")
        ]
        self.nodes = {x["package"]: x["sha256"] for x in self.chain}

    def trace(self):
        return collect_nested_field_evidence(
            self.chain, self.nodes,
            lambda p: ("Default__" + p, copy.deepcopy(self.properties[p])),
        )

    def test_partial_child_names_candidate_filters_direct(self):
        out = self.trace()
        names = out["fields"]["CompatibleAmmoNames"]
        filters = out["fields"]["AmmoSlotFilterAmounts"]
        self.assertEqual(names["resolution"], "unverified_ancestor_candidate")
        self.assertEqual(names["source_declarations_nearest_first"][0]["package"], "Parent")
        self.assertEqual(names["source_declarations_nearest_first"][0]["names"], ["LightTankAmmo"])
        self.assertEqual(filters["resolution"], "serialized_on_target")
        self.assertEqual(filters["source_declarations_nearest_first"][0]["package"], "Child")
        self.assertEqual(out["runtime_effective"], "not_established")
        self.assertEqual(names["runtime_effective"], "not_established")
        self.assertNotIn("effective_names", out)

    def test_explicit_empty_child_names_not_replaced_by_parent(self):
        self.properties["Child"]["MultiAmmo"]["CompatibleAmmoNames"] = []
        names = self.trace()["fields"]["CompatibleAmmoNames"]
        self.assertEqual(names["resolution"], "serialized_on_target")
        self.assertEqual(names["source_declarations_nearest_first"][0]["shape"],
                         "explicit_empty_array")
        self.assertEqual(names["source_declarations_nearest_first"][0]["names"], [])
        self.assertEqual(names["source_declarations_nearest_first"][1]["names"],
                         ["LightTankAmmo"])
        self.assertEqual(names["runtime_effective"], "not_established")

    def test_unsaved_child_whole_struct_only_retains_ancestor_candidate(self):
        self.properties["Child"] = {"AmmoName": "UnrelatedAmmo"}
        out = self.trace()
        self.assertEqual(out["struct_states_nearest_first"][0]["state"],
                         "struct_not_serialized")
        self.assertEqual(out["fields"]["CompatibleAmmoNames"]["resolution"],
                         "unverified_ancestor_candidate")
        self.assertEqual(out["fields"]["AmmoSlotFilterAmounts"]["resolution"],
                         "unverified_ancestor_candidate")

    def test_multiple_levels_and_nearest_distinct_field_declarations(self):
        self.properties["Parent"] = {"MultiAmmo": {"CompatibleAmmoNames": []}}
        out = self.trace()
        names = out["fields"]["CompatibleAmmoNames"]["source_declarations_nearest_first"]
        self.assertEqual([x["package"] for x in names], ["Parent", "Grandparent"])
        self.assertEqual([x["names"] for x in names], [[], ["MGAmmo"]])
        self.assertEqual(out["fields"]["AmmoSlotFilterAmounts"]["resolution"],
                         "serialized_on_target")

    def test_explicit_null_struct_blocks_transparent_inheritance_assumption(self):
        self.properties["Child"] = {"MultiAmmo": None}
        names = self.trace()["fields"]["CompatibleAmmoNames"]
        self.assertEqual(names["resolution"], "unverified_ancestor_candidate")
        self.assertEqual(names["opaque_intervening_structs"], ["Child"])
        self.assertEqual(names["runtime_effective"], "not_established")

    def test_invalid_child_struct_blocks_transparent_inheritance_assumption(self):
        self.properties["Child"] = {"MultiAmmo": "malformed"}
        names = self.trace()["fields"]["CompatibleAmmoNames"]
        self.assertEqual(names["opaque_intervening_structs"], ["Child"])
        self.assertEqual(self.trace()["struct_states_nearest_first"][0]["state"],
                         "invalid_struct")

    def test_invalid_nested_name_array_fails_to_emit_names(self):
        self.properties["Child"]["MultiAmmo"]["CompatibleAmmoNames"] = ["MGAmmo", 123]
        names = self.trace()["fields"]["CompatibleAmmoNames"]
        self.assertEqual(names["resolution"], "invalid_serialized_field")
        self.assertEqual(names["source_declarations_nearest_first"][0]["shape"],
                         "invalid_name_elements")
        self.assertNotIn("names", names["source_declarations_nearest_first"][0])

    def test_duplicate_names_are_invalid_not_silently_deduped(self):
        self.properties["Child"]["MultiAmmo"]["CompatibleAmmoNames"] = ["MGAmmo", "MGAmmo"]
        names = self.trace()["fields"]["CompatibleAmmoNames"]
        self.assertEqual(names["resolution"], "invalid_serialized_field")

    def test_non_array_field_is_invalid(self):
        self.properties["Child"]["MultiAmmo"]["CompatibleAmmoNames"] = "MGAmmo"
        names = self.trace()["fields"]["CompatibleAmmoNames"]
        self.assertEqual(names["resolution"], "invalid_serialized_field")
        self.assertEqual(names["source_declarations_nearest_first"][0]["shape"],
                         "invalid_non_array")

    def test_filter_rejects_bool_as_int(self):
        self.properties["Child"]["MultiAmmo"]["AmmoSlotFilterAmounts"] = [True]
        filters = self.trace()["fields"]["AmmoSlotFilterAmounts"]
        self.assertEqual(filters["resolution"], "invalid_serialized_field")

    def test_no_field_in_any_ancestor_reports_absence_not_empty(self):
        for p in self.properties:
            self.properties[p] = {}
        out = self.trace()
        self.assertEqual(out["fields"]["CompatibleAmmoNames"]["resolution"],
                         "no_serialized_field_on_chain")
        self.assertEqual(out["fields"]["CompatibleAmmoNames"]["source_declarations_nearest_first"], [])

    def test_changed_source_hash_fails_closed(self):
        self.nodes["Parent"] = "modified"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.trace()

    def test_missing_ancestor_node_fails_closed(self):
        self.nodes.pop("Parent")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.trace()

    def test_bad_class_default_properties_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Invalid class default"):
            collect_nested_field_evidence(
                self.chain, self.nodes, lambda _: ("Default__bad", []))

    def test_no_chain_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Empty"):
            collect_nested_field_evidence([], {}, lambda _: ("Default", {}))

    def test_json_shape_is_not_original_ue_property_type(self):
        names = self.trace()["fields"]["CompatibleAmmoNames"]
        self.assertIn("requires_independent_inspection", names["type_assertion"])
        self.assertNotIn("ue_tag_type", names)


if __name__ == "__main__":
    unittest.main()
