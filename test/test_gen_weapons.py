"""Offline regression tests for gen_weapons.py: no proprietary Foxhole assets needed."""
from __future__ import annotations

import contextlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import gen_weapons as g


class WeaponGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stats = self.root / "stats"
        self.tables = self.stats / "War" / "Content" / "Blueprints" / "Data"
        self.tables.mkdir(parents=True)
        self.sheet_path = self.root / "Weapons.json"
        self.overlay_path = self.root / "weapon_multipliers.json"
        self.original = {
            "12.7mm": {
                "Name": "12.7mm", "Dev Name": "MGAmmo",
                "Damage": "68.75", "DamageType": "HeavyKinetic",
                "Additional Names": "127;hmg",
            },
            "Ship 12.7mm (+20% HV)": {
                "Name": "Ship 12.7mm (+20% HV)", "Dev Name": "MGAmmo",
                "Damage": "82.5", "DamageType": "HeavyKinetic",
                "Additional Names": "ship mg;hv",
            },
            "Hand-entered AI shell": {
                "Name": "Hand-entered AI shell", "Dev Name": "NoAmmoData",
                "Damage": "950", "Additional Names": "hand entered",
            },
        }
        self.ammo = {"MGAmmo": {"Damage": 55, "DamageType": {"ObjectName": "HeavyKinetic"}}}
        self.weapon_mult = {"AssaultRifleHeavyW": {"DamageMultiplier": 1.2}}
        self.mount_mult = {"OtherMount": {"DamageMultiplier": 0.66}}
        self.overlay = {"Ship 12.7mm (+20% HV)": "Weapon:AssaultRifleHeavyW"}
        self.save_input()
        self.patched = (
            patch.object(g, "SHEET", self.sheet_path),
            patch.object(g, "OVERLAY", self.overlay_path),
        )
        for p in self.patched:
            p.start()
            self.addCleanup(p.stop)

    def save_table(self, name, table):
        (self.tables / (name + ".json")).write_text(
            json.dumps([{"Rows": table}]), encoding="utf-8"
        )

    def save_input(self):
        self.sheet_path.write_text(json.dumps(self.original, indent=2) + "\n", encoding="utf-8")
        self.overlay_path.write_text(json.dumps(self.overlay, indent=2) + "\n", encoding="utf-8")
        self.save_table("BPAmmoDynamicData", self.ammo)
        self.save_table("BPWeaponDynamicData", self.weapon_mult)
        self.save_table("BPMountDynamicData", self.mount_mult)

    def run_generator(self, *flags):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = g.main([str(self.stats), *flags])
        return result, output.getvalue()

    def test_damage_kinetic_and_multiplier(self):
        ammo, mult = g.load(self.stats)
        self.assertEqual(g.damage(self.original["12.7mm"], ammo, mult, self.overlay, "12.7mm"), 68.75)
        self.assertEqual(
            g.damage(self.original["Ship 12.7mm (+20% HV)"], ammo, mult, self.overlay, "Ship 12.7mm (+20% HV)"),
            82.5,
        )

    def test_kinetic_and_aircraft_factor(self):
        self.assertEqual(g.kinetic_factor("OtherAmmo", {"DamageType": {"ObjectName": "LightKinetic"}}), 1.25)
        self.assertEqual(g.kinetic_factor("AircraftAmmo", {"DamageType": {"ObjectName": "Shrapnel"}}), 1.25)
        self.assertEqual(g.kinetic_factor("ExplosiveAmmo", {"DamageType": {"ObjectName": "Explosive"}}), 1.0)

    def test_dry_run_is_read_only_and_reports_drift(self):
        self.ammo["MGAmmo"]["Damage"] = 60
        self.save_table("BPAmmoDynamicData", self.ammo)
        before = self.sheet_path.read_bytes()
        result, output = self.run_generator()
        self.assertEqual(result, 1)
        self.assertIn("12.7mm: 68.75 -> 75.0", output)
        self.assertIn("Ship 12.7mm (+20% HV): 82.5 -> 90.0", output)
        self.assertEqual(before, self.sheet_path.read_bytes())

    def test_write_updates_only_damage_values_semantically(self):
        self.ammo["MGAmmo"]["Damage"] = 60
        self.save_table("BPAmmoDynamicData", self.ammo)
        result, _ = self.run_generator("--write")
        self.assertEqual(result, 0)
        updated = json.loads(self.sheet_path.read_text(encoding="utf-8"))
        self.assertEqual(updated["12.7mm"]["Damage"], "75.0")
        self.assertEqual(updated["Ship 12.7mm (+20% HV)"]["Damage"], "90.0")
        self.assertEqual(updated["Hand-entered AI shell"], self.original["Hand-entered AI shell"])
        self.assertEqual(updated["12.7mm"]["Additional Names"], "127;hmg")

    def test_noop_write_preserves_exact_original_bytes(self):
        before = self.sheet_path.read_bytes()
        result, output = self.run_generator("--write")
        self.assertEqual(result, 0)
        self.assertIn("0 changed", output)
        self.assertEqual(self.sheet_path.read_bytes(), before)

    def test_missing_variant_mapping_refuses_write(self):
        self.overlay.clear()
        self.save_input()
        before = self.sheet_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Missing multiplier mapping"):
            self.run_generator("--write")
        self.assertEqual(self.sheet_path.read_bytes(), before)

    def test_unresolved_multiplier_refuses_write(self):
        self.overlay["Ship 12.7mm (+20% HV)"] = "Weapon:DoesNotExist"
        self.save_input()
        with self.assertRaisesRegex(ValueError, "Unresolved multiplier"):
            self.run_generator("--write")

    def test_variant_label_blocks_unrelated_multiplier_drift(self):
        self.weapon_mult["AssaultRifleHeavyW"]["DamageMultiplier"] = 1.4
        self.save_table("BPWeaponDynamicData", self.weapon_mult)
        before = self.sheet_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "inconsistent with"):
            self.run_generator("--write")
        self.assertEqual(self.sheet_path.read_bytes(), before)

    def test_bad_or_nonfinite_values_are_rejected(self):
        for value in (float("nan"), float("inf"), "nonsense", -10):
            with self.subTest(value=value):
                self.ammo["MGAmmo"]["Damage"] = value
                self.save_table("BPAmmoDynamicData", self.ammo)
                with self.assertRaises(ValueError):
                    self.run_generator("--write")

    def test_stale_overlay_entry_refuses_write(self):
        self.overlay["Old weapon no longer in sheet"] = "Weapon:AssaultRifleHeavyW"
        self.save_input()
        with self.assertRaisesRegex(ValueError, "unknown weapon"):
            self.run_generator("--write")

    def test_invalid_flags_are_rejected_instead_of_ignored(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                g.main([str(self.stats), "--wrtie"])
        self.assertEqual(raised.exception.code, 2)

    def test_seed_is_explicit_and_reports_heuristic_warning(self):
        # No auto-seeding in a regular dry run; reseeding is a manual act.
        before = self.overlay_path.read_bytes()
        result, output = self.run_generator()
        self.assertEqual(result, 0)
        self.assertEqual(self.overlay_path.read_bytes(), before)
        result, output = self.run_generator("--seed")
        self.assertEqual(result, 0)
        self.assertIn("numeric coincidences", output)
        self.assertIn("Ship 12.7mm (+20% HV)", json.loads(self.overlay_path.read_text()))

    def test_rejects_malformed_data_table(self):
        self.save_table("BPAmmoDynamicData", [])
        with self.assertRaisesRegex(ValueError, "Rows dictionary"):
            self.run_generator()


if __name__ == "__main__":
    unittest.main()
