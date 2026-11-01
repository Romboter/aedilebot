"""Synthetic regression tests for whole-build ObjectPath field discovery."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.index_blueprint_graph import build_index
from scripts.audit_blueprint_reference_surface import scan, walk


class ReferenceSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write("Data/BPAmmoDynamicData.json", [{"Rows": {"MGAmmo": {}}}])
        self.write("Data/BPMountDynamicData.json", [{"Rows": {}}])
        self.write("Vehicles/Tank.json", [
            {"Name": "Tank_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Tank_C", "Properties": {
                "ItemComponentClass": {"ObjectPath": "War/Content/Blueprints/Items/Gun.1"},
                "ExtraRefs": [{"Link": {"ObjectPath": "War/Content/Blueprints/Items/Other.0"}}],
                "External": {"ObjectPath": "/Script/War.SomeClass"},
            }},
            {"Name": "Seat1", "Type": "VehicleSeatComponent", "Properties": {
                "MountComponent": {"ObjectPath": "War/Content/Blueprints/Items/Gun.1"}}},
        ])
        self.write("Items/Gun.json", [
            {"Name": "Gun_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Gun_C", "Properties": {"AmmoName": "MGAmmo"}},
        ])
        self.write("Items/Other.json", [
            {"Name": "Other_C", "Type": "BlueprintGeneratedClass",
             "SuperStruct": {"ObjectPath": "/Script/War"}},
            {"Name": "Default__Other_C", "Properties": {}},
        ])

    def write(self, path, payload):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(payload), encoding="utf-8")

    def test_known_indexed_edges_exactly_reconfirmed_and_unknown_discovered(self):
        graph = build_index(self.root, "26058282")
        output = scan(self.root, graph)
        self.assertEqual(output["indexed_edges_verified"], 2)
        self.assertEqual(output["coverage"]["indexed"], 2)
        self.assertEqual(output["coverage"]["unindexed_blueprint"], 1)
        self.assertEqual(output["indexed_packages"], 5)
        unknown = [f for f in output["field_families"]
                   if f["counts"].get("unindexed_blueprint")]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0]["path"], "Properties.ExtraRefs[].Link")
        self.assertEqual(unknown[0]["examples"][0]["target"], "Items/Other")
        self.assertFalse(output["safe_for_unattended_publication"])

    def test_changed_export_hash_rejected(self):
        graph = build_index(self.root, "26058282")
        path = self.root / "Vehicles/Tank.json"
        path.write_text(path.read_text() + " ", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash"):
            scan(self.root, graph)

    def test_tampered_graph_digest_fails_closed(self):
        graph = build_index(self.root, "26058282")
        graph["object_references"].pop()
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            scan(self.root, graph)

    def test_index_claim_missing_edge_rejected(self):
        graph = build_index(self.root, "26058282")
        graph["object_references"][0]["field"] = "AnotherProperty"
        from scripts.index_blueprint_graph import digest
        graph["relation_digest"] = digest({
            "objects": [{k: e[k] for k in
                          ("source", "record", "field", "object_path", "target", "status")}
                        for e in graph["object_references"]],
            "rows": [{k: e[k] for k in
                      ("source", "record", "field", "table", "row", "status")}
                     for e in graph["numeric_row_references"]],
            "declarations": [{k: e[k] for k in ("source", "record", "field", "value")}
                             for e in graph["declarations"]],
        })
        with self.assertRaisesRegex(ValueError, "absent"):
            scan(self.root, graph)

    def test_reference_bound_aborts_not_partial_success(self):
        with self.assertRaisesRegex(ValueError, "Too many"):
            scan(self.root, build_index(self.root, "26058282"), max_refs=1)

    def test_nested_lists_retain_source_field_positions(self):
        fields = list(walk({"Properties": {"Modes": [
            {"Sub": {"ObjectPath": "one"}},
            {"Sub": {"ObjectPath": "two"}},
        ]}}))
        self.assertEqual(fields, [
            ("Properties.Modes[0].Sub", "one"),
            ("Properties.Modes[1].Sub", "two"),
        ])

    def test_recursion_depth_rejected(self):
        value = {"x": {"y": {"z": {"ObjectPath": "one"}}}}
        with self.assertRaisesRegex(ValueError, "nesting"):
            list(walk(value, depth=30))


if __name__ == "__main__":
    unittest.main()
