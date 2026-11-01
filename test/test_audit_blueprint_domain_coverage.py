"""Synthetic, source-only Blueprint domain coverage regression tests."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_blueprint_domain_coverage import domain, normalized, scan
from scripts.index_blueprint_graph import build_index


class DomainCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {"MGAmmo": {}}}])
        self.write("Data/BPMountDynamicData.json", [{"Rows": {}}])
        self.write("Vehicles/BPTank.json", [
            {"Name": "BPTank_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War.Vehicle"}},
            {"Name": "Default__BPTank_C", "Properties": {}},
            {"Name": "TankSeat", "Type": "VehicleSeatComponent", "Properties": {
                "MountComponent": {"ObjectPath": "War/Content/Blueprints/Items/BPGun.0"}}},
        ])
        self.write("Items/BPGun.json", [
            {"Name": "BPGun_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War.Weapon"}},
            {"Name": "Default__BPGun_C", "Properties": {
                "AmmoName": "MGAmmo",
                "ProjectileClass": {
                    "ObjectPath": "War/Content/Blueprints/Items/BPShell.0"},
            }},
        ])
        self.write("Items/BPShell.json", [
            {"Name": "BPShell_C", "Type": "BlueprintGeneratedClass"},
            {"Name": "Default__BPShell_C", "Properties": {}},
        ])
        self.write("Structures/BPPillbox.json", [
            {"Name": "BPPillbox_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War.Defense"}},
            {"Name": "Default__BPPillbox_C", "Properties": {
                "RepairRate": 20,
                "TurretMountClass": {"ObjectPath":
                    "War/Content/Blueprints/Items/BPGun.0"},
                "Native": {"ObjectPath": "/Script/War.SomeNativeClass"},
            }},
            {"Name": "PillboxHealth", "Type": "HealthComponent",
             "Properties": {"DamageResistance": 1.5}},
        ])

    def write(self, path, data):
        filename = self.root / path
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text(json.dumps(data), encoding="utf-8")

    def test_source_edges_and_unindexed_structure_candidates_are_separate(self):
        report = scan(self.root, build_index(self.root, "26058282"))
        coverage = report["coverage"]
        self.assertEqual(coverage["packages"], 6)
        self.assertEqual(coverage["source_object_references_checked"], 2)
        self.assertEqual(coverage["domains"]["structures_path"]["packages"], 1)
        self.assertEqual(
            coverage["domains"]["structures_path"]["unindexed_blueprint"], 1)
        self.assertEqual(
            coverage["domains"]["structures_path"]["native_or_external"], 2)
        self.assertEqual(coverage["domains"]["structures_path"]["generated_class_with_one_saved_default"], 1)
        self.assertEqual(coverage["domains"]["items_path"]["indexed_exact_row_present_source_only"], 1)
        self.assertFalse(report["safe_for_unattended_publication"])
        family = next(f for f in report["top_unindexed_blueprint_reference_families"]
                      if f["field"] == "Properties.TurretMountClass")
        self.assertEqual(family["examples"][0]["target"], "Items/BPGun")
        self.assertEqual(family["domain"], "structures_path")
        self.assertTrue(any(x["name"] == "RepairRate" for x in
                            coverage["saved_default_fields_by_domain"]["structures_path"]))

    def test_changed_source_is_rejected(self):
        graph = build_index(self.root, "26058282")
        source = self.root / "Structures/BPPillbox.json"
        source.write_text(source.read_text() + " ", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash"):
            scan(self.root, graph)

    def test_changed_relation_digest_is_rejected(self):
        graph = build_index(self.root, "26058282")
        graph["object_references"].pop()
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            scan(self.root, graph)

    def test_scan_bound_rejects_incomplete_inventory(self):
        with self.assertRaisesRegex(ValueError, "bound"):
            scan(self.root, build_index(self.root, "26058282"), max_refs=1)

    def test_names_do_not_prove_gameplay_domain(self):
        self.assertEqual(domain("Items/BPMachineGun"), "items_path")
        self.assertEqual(domain("Unclassified/BPPillbox"), "other_path")
        self.assertEqual(domain("Defenses/BPBunker"), "defenses_path")
        self.assertEqual(normalized("Properties.Configs[2].Muzzles[0]"),
                         "Properties.Configs[].Muzzles[]")


if __name__ == "__main__":
    unittest.main()
