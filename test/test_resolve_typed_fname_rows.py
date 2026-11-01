"""Synthetic tests: typed FName matches require independently inspected source fields."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.index_blueprint_graph import build_index
from scripts.resolve_typed_fname_rows import resolve, parse_inspection


BUILD = "26058282"
PAK_SHA256 = "a" * 64
PREFIX = "War/Content/Blueprints/"


class TypedFNameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {
            "RpgAmmo": {"Damage": 350},
            "LightTankAmmo": {"Damage": 600},
            "MGAmmo": {"Damage": 55},
        }}])
        self.put("Data/BPMountDynamicData.json", [{"Rows": {
            "HalfTrackMultiWGunner": {"DamageMultiplier": 1.0},
        }}])
        self.put("Items/RPG.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "RPG_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__RPG_C", "Properties": {
                "CompatibleAmmoCodeName": "RPGAmmo",
            }},
        ])
        self.put("Vehicles/Submarine.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Submarine_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Submarine_C", "Properties": {
                "MultiAmmo": {"CompatibleAmmoNames": ["lighttankammo"]},
            }},
        ])
        self.put("Vehicles/Halftrack.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Halftrack_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Type": "VehicleSeatComponent", "Name": "PassengerSeat1_GEN_VARIABLE",
             "Properties": {"MountCodeName": "HalftrackMultiWGunner"}},
        ])

    def put(self, relative, payload):
        p = self.root / relative
        p.parent.mkdir(exist_ok=True, parents=True)
        p.write_text(json.dumps(payload), encoding="utf-8")

    def inspection(self):
        def kind(package, record, field):
            return f"TYPE\t{PREFIX}{package}.uasset\t{record}\t{field}\tNameProperty"
        return "\n".join([
            "provider ready: 12000 files",
            f"TABLE\t{PREFIX}Data/BPAmmoDynamicData.uasset\tBPAmmoDynamicData\tFName",
            f"TABLE\t{PREFIX}Data/BPMountDynamicData.uasset\tBPMountDynamicData\tFName",
            kind("Items/RPG", "Default__RPG_C", "CompatibleAmmoCodeName"),
            kind("Vehicles/Submarine", "Default__Submarine_C", "MultiAmmo.CompatibleAmmoNames[0]"),
            kind("Vehicles/Halftrack", "PassengerSeat1_GEN_VARIABLE", "MountCodeName"),
            "inspect-types: 3 tagged identity properties in 5 packages",
        ])

    def run_resolver(self, type_text=None, index=None):
        return resolve(index or build_index(self.root, BUILD), self.root,
                       self.inspection() if type_text is None else type_text,
                       BUILD, PAK_SHA256)

    def test_three_explicit_typed_fnames_resolve_uniquely_without_damage(self):
        result = self.run_resolver()
        self.assertEqual(result["counts"]["eligible_and_unique"], 3)
        self.assertEqual(result["counts"]["unresolved"], 0)
        matches = {entry["declared_row"]: entry for entry in result["observations"]}
        self.assertEqual(matches["RPGAmmo"]["matched_row"], "RpgAmmo")
        self.assertEqual(matches["lighttankammo"]["matched_row"], "LightTankAmmo")
        self.assertEqual(matches["HalftrackMultiWGunner"]["matched_row"],
                         "HalfTrackMultiWGunner")
        self.assertFalse(result["safe_for_unattended_publication"])
        self.assertTrue(all(not obj["safe_for_unattended_publication"] for obj in matches.values()))
        self.assertTrue(all("damage" not in obj for obj in matches.values()))

    def test_without_field_type_proof_case_match_stays_unresolved(self):
        types = self.inspection().replace(
            "TYPE\t"+PREFIX+"Items/RPG.uasset\tDefault__RPG_C\tCompatibleAmmoCodeName\tNameProperty\n", "")
        report = self.run_resolver(types)
        match = next(e for e in report["observations"] if e["declared_row"] == "RPGAmmo")
        self.assertEqual(match["reason"], "original_nameproperty_type_unverified")
        self.assertIsNone(match["matched_row"])

    def test_wrong_property_type_does_not_promote_case_match(self):
        types = self.inspection().replace("CompatibleAmmoCodeName\tNameProperty",
                                          "CompatibleAmmoCodeName\tStrProperty")
        report = self.run_resolver(types)
        entry = next(e for e in report["observations"] if e["declared_row"] == "RPGAmmo")
        self.assertEqual(entry["reason"], "original_nameproperty_type_unverified")

    def test_table_key_type_requires_proof(self):
        types = self.inspection().replace("BPAmmoDynamicData\tFName",
                                          "BPAmmoDynamicData\tString")
        report = self.run_resolver(types)
        rpg = next(e for e in report["observations"] if e["declared_row"] == "RPGAmmo")
        self.assertEqual(rpg["reason"], "datatable_fname_key_unverified")

    def test_ambiguous_casefold_rows_fail_closed(self):
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {
            "RpgAmmo": {"Damage": 350}, "RPGAMMO": {"Damage": 300},
            "LightTankAmmo": {"Damage": 600},
        }}])
        report = self.run_resolver()
        rpg = next(e for e in report["observations"] if e["declared_row"] == "RPGAmmo")
        self.assertEqual(rpg["reason"], "ambiguous_fname_row_keys")
        self.assertEqual(rpg["candidate_rows"], ["RPGAMMO", "RpgAmmo"])
        self.assertIsNone(rpg["matched_row"])

    def test_missing_casefold_rows_remain_missing(self):
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {
            "DifferentAmmo": {"Damage": 400}, "LightTankAmmo": {"Damage": 600},
        }}])
        report = self.run_resolver()
        rpg = next(e for e in report["observations"] if e["declared_row"] == "RPGAmmo")
        self.assertEqual(rpg["reason"], "no_matching_named_row")

    def test_unparseable_multi_ammo_is_not_a_casefold_candidate(self):
        self.put("Vehicles/Submarine.json", [
            {"Name": "Default__Submarine_C", "Properties": {"MultiAmmo": None}},
        ])
        report = self.run_resolver()
        field = next(e for e in report["observations"] if e["source"] == "Vehicles/Submarine")
        self.assertEqual(field["reason"], "no_compatible_ammo_names_exported")

    def test_unset_fname_none_seat_is_not_a_missing_weapon(self):
        self.put("Vehicles/Driver.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Driver_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Type": "VehicleSeatComponent", "Name": "DriverSeat0_GEN_VARIABLE",
             "Properties": {"MountCodeName": "None"}},
        ])
        graph = build_index(self.root, BUILD)
        name = next(e for e in graph["numeric_row_references"]
                    if e["source"] == "Vehicles/Driver" and e["field"] == "MountCodeName")
        self.assertEqual(name["status"], "none_sentinel_candidate")
        tag = (f"TYPE\\t{PREFIX}Vehicles/Driver.uasset\\tDriverSeat0_GEN_VARIABLE"
               f"\\tMountCodeName\\tNameProperty")
        result = self.run_resolver(self.inspection() + "\\n" + tag, index=graph)
        sentinel = next(e for e in result["observations"] if e["source"] == "Vehicles/Driver")
        self.assertEqual(sentinel["status"], "typed_fname_unset_mount_identity")
        self.assertEqual(sentinel["reason"], "ue_fname_none_unset_mount_identity")
        self.assertIsNone(sentinel["matched_row"])
        self.assertEqual(result["counts"]["unset_mount_identity"], 1)

    def test_none_seat_without_original_type_proof_stays_unresolved(self):
        self.put("Vehicles/Driver.json", [
            {"Type": "BlueprintGeneratedClass", "Name": "Driver_C",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Type": "VehicleSeatComponent", "Name": "DriverSeat0_GEN_VARIABLE",
             "Properties": {"MountCodeName": "None"}},
        ])
        result = self.run_resolver()
        sentinel = next(e for e in result["observations"] if e["source"] == "Vehicles/Driver")
        self.assertEqual(sentinel["reason"], "unset_mount_nameproperty_type_unverified")
        self.assertEqual(sentinel["status"], "unresolved")

    def test_mismatched_index_table_hash_aborts(self):
        index = build_index(self.root, BUILD)
        self.put("Data/BPAmmoDynamicData.json", [{"Rows": {"RpgAmmo": {}}}])
        with self.assertRaisesRegex(ValueError, "checksum mismatches"):
            self.run_resolver(index=index)

    def test_mismatched_source_blueprint_hash_aborts(self):
        index = build_index(self.root, BUILD)
        self.put("Items/RPG.json", [
            {"Name": "Default__RPG_C", "Properties": {
                "CompatibleAmmoCodeName": "RPGAmmo",
                "UnrelatedAssetProperty": 42,
            }},
        ])
        with self.assertRaisesRegex(ValueError, "Source Blueprint checksum"):
            self.run_resolver(index=index)

    def test_mismatched_index_build_rejected(self):
        index = build_index(self.root, "26058300")
        with self.assertRaisesRegex(ValueError, "build differ"):
            self.run_resolver(index=index)

    def test_invalid_or_duplicate_inspector_records_fail(self):
        with self.assertRaisesRegex(ValueError, "Duplicate TYPE"):
            self.run_resolver(self.inspection()+"\n"+self.inspection().splitlines()[3])
        with self.assertRaisesRegex(ValueError, "Malformed TABLE"):
            parse_inspection("TABLE\tbad")

    def test_pak_checksum_format_required(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            resolve(build_index(self.root, BUILD), self.root,
                    self.inspection(), BUILD, "not-a-digest")


if __name__ == "__main__":
    unittest.main()
