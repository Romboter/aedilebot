"""Build-wide MultiAmmo source audit on deterministic synthetic graph exports."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.audit_multi_ammo_declarations import audit
from scripts.index_blueprint_graph import build_index


class WholeBuildMultiAmmoAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {"MGAmmo": {"Damage": 5}}}])
        self.put("Data/BPMountDynamicData.json", [{"Rows": {}}])
        self.blueprint("Items/Base", "/Script/War",
                       {"MultiAmmo": {"CompatibleAmmoNames": ["MGAmmo"]}})
        self.blueprint("Items/Child", "War/Content/Blueprints/Items/Base.1",
                       {"MultiAmmo": {"AmmoSlotFilterAmounts": [1, 2]}})
        self.blueprint("Items/EmptyChild", "War/Content/Blueprints/Items/Base.1",
                       {"MultiAmmo": {"CompatibleAmmoNames": []}})
        self.blueprint("Items/Grandchild", "War/Content/Blueprints/Items/Child.1",
                       {"AmmoName": "MGAmmo"})

    def put(self, path, obj):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(obj), encoding="utf-8")

    def blueprint(self, package, parent, props):
        name = package.split("/")[-1]
        self.put(package + ".json", [
            {"Name": name + "_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": parent}},
            {"Name": "Default__" + name + "_C", "Properties": props},
        ])

    def scan(self, index=None):
        if index is None:
            index = build_index(self.root, "26058282")
        return audit(self.root, index)

    def test_discovers_all_explicit_not_only_four_preselected_targets(self):
        report = self.scan()
        entries = {x["component"]: x for x in report["declarations"]}
        self.assertEqual(len(entries), 3)
        self.assertNotIn("Items/Grandchild", entries)
        self.assertEqual(report["coverage"]["blueprint_packages_in_index"], 6)
        self.assertEqual(report["coverage"]["counts"]["partial_with_parent_candidate"], 1)
        self.assertEqual(report["coverage"]["counts"]["incomplete_or_empty_with_parent_candidate"], 2)
        self.assertEqual(entries["Items/Child"]["saved_shape"], "array_not_in_export")
        self.assertEqual(entries["Items/Child"]["parent_name_candidate"]["package"], "Items/Base")
        self.assertEqual(entries["Items/EmptyChild"]["saved_shape"], "empty_array")
        self.assertEqual(entries["Items/EmptyChild"]["compatible_names_field_resolution"],
                         "serialized_on_target")
        self.assertTrue(all(x["effective_at_runtime"] == "not_established"
                            for x in entries.values()))
        self.assertFalse(report["safe_for_unattended_publication"])

    def test_changed_game_asset_hash_aborts(self):
        index = build_index(self.root, "26058282")
        self.blueprint("Items/Child", "War/Content/Blueprints/Items/Base.1",
                       {"MultiAmmo": {"AmmoSlotFilterAmounts": [5]}})
        with self.assertRaisesRegex(ValueError, "hash"):
            self.scan(index)

    def test_missing_parent_fails_closed(self):
        self.blueprint("Items/Child", "War/Content/Blueprints/Items/Nonexistent.1",
                       {"MultiAmmo": {"AmmoSlotFilterAmounts": [1]}})
        with self.assertRaisesRegex(ValueError, "parent Blueprint export missing"):
            self.scan()

    def test_full_source_names_are_not_parent_candidates(self):
        self.blueprint("Items/Child", "War/Content/Blueprints/Items/Base.1",
                       {"MultiAmmo": {"CompatibleAmmoNames": ["MGAmmo"]}})
        record = {x["component"]: x for x in self.scan()["declarations"]}["Items/Child"]
        self.assertEqual(record["saved_shape"], "explicit_ammo_options")
        self.assertEqual(record["compatible_names_field_resolution"], "serialized_on_target")
        self.assertEqual(record["effective_at_runtime"], "not_established")


if __name__ == "__main__":
    unittest.main()
