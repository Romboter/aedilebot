"""Synthetic tests for deterministic Blueprint graph indexing and build drift."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.index_blueprint_graph import build_index
from scripts.diff_blueprint_graph import compare


class GraphIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {
            "MGAmmo": {"Damage": 55},
            "AircraftAmmo": {"Damage": 65},
            "SmokeAmmo": {"Damage": 0},
        }}])
        self.put("Data/BPMountDynamicData.json", [{"Rows": {
            "TankGunner": {"DamageMultiplier": 1.2},
            "AircraftFighterW_HMG": {"DamageMultiplier": 1.0},
        }}])
        self.put("Vehicles/Base.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Base_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Base_C", "Properties": {
                "CodeName": "SomeVehicle",
                "WeaponConfigs": [{"AmmoCodeName": "AircraftAmmo",
                                   "WeaponCodeName": "AircraftFighterW_HMG"}],
            }},
            {"Type": "VehicleSeatComponent", "Name": "GunnerSeat1_GEN_VARIABLE",
             "Properties": {"MountCodeName": "TankGunner",
                            "MountComponent": {"ObjectPath": "War/Content/Blueprints/Vehicles/Turret.0"}}},
        ])
        self.put("Vehicles/Child.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Child_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Vehicles/Base.1"}},
            {"Name": "Default__Child_C", "Properties": {"DisplayName": "Child"}},
        ])
        self.put("Vehicles/Turret.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Turret_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Turret_C", "Properties": {
                "AmmoName": "MGAmmo",
                "MultiAmmo": {"CompatibleAmmoNames": ["MGAmmo", "SmokeAmmo"]},
                "GrenadeClasses": [
                    {"ObjectPath": "War/Content/Blueprints/Items/ProjectileMissing.0"}],
            }},
        ])

    def put(self, relative, content, indent=None):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(content, indent=indent), encoding="utf-8")

    def index(self, build="26058282"):
        return build_index(self.root, build)

    def test_source_edges_and_named_rows_not_numeric_proxies(self):
        graph = self.index()
        self.assertEqual(graph["coverage"]["object_reference_status"]["missing_export"], 1)
        self.assertEqual(graph["coverage"]["object_reference_status"]["exported"], 2)
        self.assertEqual(graph["coverage"]["numeric_row_status"]["row_present"], 6)
        self.assertEqual(graph["coverage"]["declared_identifiers"], 1)
        missing = [e for e in graph["object_references"] if e["status"] == "missing_export"]
        self.assertEqual(missing[0]["target"], "Items/ProjectileMissing")
        seats = [e for e in graph["numeric_row_references"] if e["field"] == "MountCodeName"]
        self.assertEqual(seats[0]["table"], "BPMountDynamicData")
        self.assertEqual(seats[0]["row"], "TankGunner")
        self.assertTrue(all(not e.get("damage") for e in graph["numeric_row_references"]))
        self.assertFalse(graph["safe_for_unattended_publication"])

    def test_missing_ammorow_never_borrows_other_row(self):
        self.put("Vehicles/Turret.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Turret_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Turret_C", "Properties": {"AmmoName": "RPGAmmo"}},
        ])
        graph = self.index()
        ref = next(e for e in graph["numeric_row_references"]
                   if e["source"] == "Vehicles/Turret" and e["field"] == "AmmoName")
        self.assertEqual(ref["row"], "RPGAmmo")
        self.assertEqual(ref["status"], "row_missing")

    def test_absent_table_is_not_absent_named_row(self):
        (self.root / "Data/BPMountDynamicData.json").unlink()
        graph = self.index()
        refs = [e for e in graph["numeric_row_references"]
                if e["table"] == "BPMountDynamicData"]
        self.assertTrue(refs)
        self.assertTrue(all(x["status"] == "table_unavailable" for x in refs))

    def test_same_relationships_different_export_format_same_semantic_digest(self):
        old = self.index()
        p = self.root / "Vehicles/Child.json"
        self.put("Vehicles/Child.json", json.loads(p.read_text()), indent=2)
        new = self.index()
        self.assertEqual(old["relation_digest"], new["relation_digest"])
        drift = compare(old, new)
        self.assertEqual(drift["counts"]["relationship_changes"], 0)
        self.assertEqual(drift["counts"]["content_changes"], 1)
        self.assertTrue(drift["requires_human_review"])

    def test_changed_mount_reference_and_missing_table_row_flagged(self):
        old = self.index()
        p = self.root / "Vehicles/Base.json"
        objects = json.loads(p.read_text())
        objects[2]["Properties"]["MountCodeName"] = "OtherMount"
        self.put("Vehicles/Base.json", objects)
        changed = compare(old, self.index("26058300"))
        self.assertTrue(changed["build_changed"])
        self.assertTrue(changed["requires_human_review"])
        affected = [e for e in changed["relationship_changes"]
                    if e["source_identity"].get("field") == "MountCodeName"]
        self.assertEqual(len(affected), 1)
        self.assertEqual(affected[0]["before"]["row"], "TankGunner")
        self.assertEqual(affected[0]["after"]["row"], "OtherMount")
        self.assertEqual(affected[0]["after"]["status"], "row_missing")

    def test_changed_parent_path_reports_relationship_drift(self):
        old = self.index()
        self.put("Vehicles/Child.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Child_C",
             "SuperStruct": {"ObjectPath": "War/Content/Blueprints/Vehicles/OtherParent.1"}},
            {"Name": "Default__Child_C", "Properties": {"DisplayName": "Child"}},
        ])
        result = compare(old, self.index("26058300"))
        self.assertEqual(result["counts"]["by_family"]["object_reference_changed"], 1)
        self.assertEqual(next(e for e in result["relationship_changes"]
                              if e["family"] == "object_reference")["after"]["target"],
                         "Vehicles/OtherParent")

    def test_new_build_requires_review_even_if_references_equal(self):
        before = self.index("26058282")
        after = self.index("26058283")
        drift = compare(before, after)
        self.assertEqual(drift["counts"]["relationship_changes"], 0)
        self.assertEqual(drift["counts"]["content_changes"], 0)
        self.assertTrue(drift["build_changed"])
        self.assertTrue(drift["requires_human_review"])
        self.assertFalse(drift["safe_for_unattended_publication"])

    def test_unchanged_snapshot_is_stable(self):
        old = self.index()
        self.assertEqual(old, self.index())
        self.assertFalse(compare(old, old)["requires_human_review"])

    def test_corrupt_fingerprint_and_duplicate_refs_rejected(self):
        index = self.index()
        modified = copy.deepcopy(index)
        modified["relation_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            compare(index, modified)
        modified = copy.deepcopy(index)
        modified["numeric_row_references"].append(
            copy.deepcopy(modified["numeric_row_references"][0]))
        with self.assertRaises(ValueError):
            compare(index, modified)

    def test_case_only_spelling_is_diagnostic_not_a_row_join(self):
        self.put("Vehicles/Turret.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Turret_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Turret_C", "Properties": {"AmmoName": "mgammo"}},
        ])
        graph = self.index()
        ref = next(x for x in graph["numeric_row_references"]
                   if x["source"] == "Vehicles/Turret" and x["field"] == "AmmoName")
        self.assertEqual(ref["status"], "row_missing")
        self.assertEqual(ref["row"], "mgammo")
        self.assertEqual(ref["case_only_spelling_candidates_unverified"], ["MGAmmo"])
        self.assertFalse(graph["safe_for_unattended_publication"])

    def test_unknown_game_or_empty_export_fails(self):
        with self.assertRaises(ValueError):
            build_index(self.root, "unknown")
        with self.assertRaises(ValueError):
            build_index(self.root, "26058282", max_packages=1)

    def test_malformed_multi_ammo_is_explicitly_invalid(self):
        self.put("Vehicles/Turret.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Turret_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Turret_C", "Properties": {
                "GrenadeMultiAmmo": {"CompatibleAmmoNames": ["MGAmmo", 22]},
            }},
        ])
        graph = self.index()
        refs = [r for r in graph["numeric_row_references"]
                if r["source"] == "Vehicles/Turret"]
        self.assertEqual([x["status"] for x in refs], ["row_present", "invalid_identifier"])


if __name__ == "__main__":
    unittest.main()
