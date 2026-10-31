import zstandard as zstd
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from archive_exports import archive_run


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.export = self.root / "export" / "_json"
        self.archive = self.root / "archive"
        self.export.mkdir(parents=True)
        self.inventory = self.root / "output" / "map-inventory.json"
        self.inventory.parent.mkdir()
        self.pak = self.root / "game.pak"
        self.pak.write_bytes(b"test game pak")
        self.contents = {
            "AcrithiaHex": b'{"blueprints":{"BPDestroyedRelicBase_C":[{"_self":[1,2,3]}]}}',
            "LykosIsleHex": b'{"blueprints":{"BPTownBase_C":[{"_self":[4,5,6]}]},"future":123}',
        }
        self.refresh_inventory()

    def refresh_inventory(self):
        rows = []
        for name, data in sorted(self.contents.items()):
            (self.export / (name + ".json")).write_bytes(data)
            rows.append({
                "map": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            })
        self.inventory.write_text(json.dumps({"maps": rows}), encoding="utf-8")

    def run_archive(self):
        manifest = archive_run(self.export, self.inventory, self.archive, "pinned-commit", self.pak, "test")
        return json.loads(manifest.read_text(encoding="utf-8"))

    def test_all_maps_archived_exactly_with_unmodified_properties(self):
        manifest = self.run_archive()
        self.assertEqual(manifest["map_count"], 2)
        self.assertFalse(manifest["full_actor_property_coverage_verified"])
        self.assertEqual(manifest["source_format"], "fh_map_exporter-processed-json-v1")
        self.assertEqual(manifest["compression"], "zstd")
        self.assertEqual(manifest["compression_level"], 15)
        self.assertTrue(all(entry["blob"].endswith(".json.zst") for entry in manifest["maps"]))
        for item in manifest["maps"]:
            archived = self.archive / item["blob"]
            with archived.open("rb") as handle, zstd.ZstdDecompressor().stream_reader(handle) as reader:
                self.assertEqual(reader.read(), self.contents[item["name"]])
        latest = json.loads((self.archive / "latest.json").read_text(encoding="utf-8"))
        self.assertTrue((self.archive / latest["run_manifest"]).is_file())
        self.assertEqual(len(list((self.archive / "runs").glob("*.json"))), 1)

    def test_unchanged_runs_share_blobs_but_retain_separate_manifests(self):
        self.run_archive()
        self.run_archive()
        self.assertEqual(len(list((self.archive / "blobs").rglob("*.json.zst"))), 2)
        self.assertEqual(len(list((self.archive / "runs").glob("*.json"))), 2)

    def test_changed_map_creates_new_blob_without_overwriting_old_map(self):
        original = self.run_archive()
        self.contents["AcrithiaHex"] = b'{"blueprints":{"BPDestroyedRelicBase_C":[{"_self":[7,8,9]}]}}'
        self.refresh_inventory()
        changed = self.run_archive()
        self.assertEqual(len(list((self.archive / "blobs").rglob("*.json.zst"))), 3)
        previous = next(m for m in original["maps"] if m["name"] == "AcrithiaHex")
        current = next(m for m in changed["maps"] if m["name"] == "AcrithiaHex")
        with (self.archive / previous["blob"]).open("rb") as f, zstd.ZstdDecompressor().stream_reader(f) as reader:
            self.assertNotEqual(reader.read(), self.contents["AcrithiaHex"])
        with (self.archive / current["blob"]).open("rb") as f, zstd.ZstdDecompressor().stream_reader(f) as reader:
            self.assertEqual(reader.read(), self.contents["AcrithiaHex"])

    def test_stale_inventory_does_not_publish_latest_or_manifest(self):
        (self.export / "AcrithiaHex.json").write_text('{"changed": true}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs from validated inventory"):
            self.run_archive()
        self.assertFalse((self.archive / "latest.json").exists())

    def test_missing_map_fails_instead_of_archiving_incomplete_snapshot(self):
        (self.export / "LykosIsleHex.json").unlink()
        with self.assertRaisesRegex(ValueError, "does not match the complete map"):
            self.run_archive()
        self.assertFalse((self.archive / "latest.json").exists())

    def test_archive_cannot_live_below_working_export(self):
        with self.assertRaisesRegex(ValueError, "must be separate"):
            archive_run(
                self.export, self.inventory, self.export / "archive",
                "pinned-commit", self.pak,
            )


if __name__ == "__main__":
    unittest.main()
