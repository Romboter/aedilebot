import json
import tempfile
import unittest
from pathlib import Path
from .inventory import make_inventory, inventory_map


class InventoryTests(unittest.TestCase):
    def test_candidates_are_diagnostic_and_support_diff(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            example = directory / "LykosIsleHex.json"
            example.write_text(json.dumps({
                "blueprints": {
                    "BPDestroyedRelicBase_C": [{"_self": [1, 2, 3]}],
                    "BPTownBase1_C": [{"_self": [4, 5, 6]}, {"_self": [7, 8, 9]}],
                    "OtherBuilding_C": [{}],
                },
                "symbols": {},
            }), encoding="utf-8")
            result = make_inventory(directory)
            self.assertEqual(result["map_count"], 1)
            self.assertEqual(result["candidate_relic_count"], 1)
            self.assertEqual(result["candidate_town_count"], 2)
            self.assertEqual(result["changed_maps"], ["LykosIsleHex"])
            self.assertEqual(make_inventory(directory, result)["changed_maps"], [])

    def test_fails_on_incompatible_or_empty_export(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            with self.assertRaises(ValueError):
                make_inventory(directory)
            file = directory / "Broken.json"
            file.write_text('{"actors": []}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expected a CUE4Parse export"):
                inventory_map(file)


if __name__ == "__main__":
    unittest.main()
