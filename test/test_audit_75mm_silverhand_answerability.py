"""Fixture tests for player-query evidence; no game assets required."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.audit_75mm_silverhand_answerability import check, legacy_hits, source_ref, saved_enum


class SilverhandAnswerabilityTests(unittest.TestCase):
    def setUp(self):
        self.weapon = {"75mm": {"Dev Name": "BattleTankAmmo", "Damage": "1750.0",
                                "DamageType": "Explosive"}}
        self.target = {"Silverhand - Mk. IV (SvH)": {"Dev Name": "MediumTankW",
                       "Health": "3100", "Mitigation Type": "Tier2Tank"}}
        self.damage = {"Explosive": {"Tier2Tank": "0.15"}}

    def build_fixture(self, folder: Path, *, damage=1750, health=3100, tier=0.15,
                      enum="EDamageType::Explosive", codename="MediumTankW"):
        sources = folder / "Data"
        sources.mkdir()
        for name, rows in {
            "BPAmmoDynamicData": {"BattleTankAmmo": {"Damage": damage,
                "DamageType": {"ObjectPath": ("War/Content/Blueprints/DamageTypes/"
                                               "BPExplosiveDamageType.BPExplosiveDamageType_C")}}},
            "DTDamageProfiles": {"Explosive": {"Tier2Tank": tier}},
            "BPVehicleDynamicData": {"MediumTankW": {"MaxHealth": health}},
            "BPStructureDynamicData": {},
        }.items():
            (sources / (name + ".json")).write_text(json.dumps(
                [{"Type": "DataTable", "Name": name, "Rows": rows}]))
        types = folder / "DamageTypes"
        types.mkdir()
        (types / "BPExplosiveDamageType.json").write_text(json.dumps([
            {"Type": "BlueprintGeneratedClass", "Name": "BPExplosiveDamageType_C"},
            {"Name": "Default__BPExplosiveDamageType_C", "Type": "Custom", "Properties": {
                "Type": enum}}]))
        vehicles = folder / "Vehicles"
        vehicles.mkdir()
        (vehicles / "BPMediumTankW.json").write_text(json.dumps([
            {"Name": "Default__BPMediumTankW_C", "Type": "Custom", "Properties": {
                "CodeName": codename, "ArmourType": "Tier2Tank", "MaxHealth": health}}]))

    def test_legacy_calculation_3_hits(self):
        result = legacy_hits(self.weapon["75mm"], self.target["Silverhand - Mk. IV (SvH)"],
                             self.damage)
        self.assertEqual(result["legacy_damage_per_hit"], 1488)
        self.assertEqual(result["legacy_hits_to_kill"], 3)

    def test_realistic_fixture_exact_source(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            self.build_fixture(folder)
            result = check(folder, self.weapon, self.target, self.damage, "26058282")
            states = result["source_statuses"]
            self.assertEqual(states["ammo_base_damage_vs_human"], "match")
            self.assertEqual(states["enum_to_profile_row"], "unique_exact")
            self.assertEqual(states["profile_target_column_vs_human"], "match")
            self.assertEqual(states["target_source_health_match"], "some_saved_source_field")
            self.assertEqual(states["vehicle_saved_codename_defaults"], "unique")
            self.assertEqual(result["runtime_rules"]["penetration"], "unverified")
            self.assertEqual(result["answerability"], "blocked-inherited-target-category-proof")
            ancestry = {
                "source_status": "exact_saved_ancestor_declaration_matches_human",
                "native_effective_inheritance": "unverified",
                "leaf": "Vehicles/MediumTank/BPMediumTankW",
                "human_target_category": "Tier2Tank",
            }
            verified = check(folder, self.weapon, self.target, self.damage,
                             "26058282", ancestry)
            self.assertEqual(verified["answerability"], "answerable-with-stated-assumptions")


    def test_mismatch_not_silently_promoted(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            self.build_fixture(folder, damage=999, health=3101, tier=0.25, enum="EDamageType::Different",
                               codename="WrongTarget")
            result = check(folder, self.weapon, self.target, self.damage, "26058282")
            states = result["source_statuses"]
            self.assertEqual(states["ammo_base_damage_vs_human"], "mismatch")
            self.assertEqual(states["enum_to_profile_row"], "unresolved")
            self.assertEqual(states["vehicle_saved_codename_defaults"], "none")
            self.assertEqual(states["target_source_health_match"], "unresolved")
            self.assertEqual(result["answerability"], "blocked-missing-source-evidence")

    def test_actual_legacy_calculator_output(self):
        """Run the existing calculator functions with bot imports stubbed, not a replica."""
        import importlib.util
        from unittest.mock import patch
        import types

        root = Path(__file__).resolve().parents[1]
        weapons = json.loads((root / "data/Weapons.json").read_text(encoding="utf-8"))
        targets = json.loads((root / "data/Targets.json").read_text(encoding="utf-8"))
        damages = json.loads((root / "data/Damage.json").read_text(encoding="utf-8"))
        mocked = {
            "parse": types.SimpleNamespace(weapons=weapons, targets=targets, damages=damages),
            "utils": types.SimpleNamespace(debug_summary=lambda *a, **kw: None),
            "fuzzy": types.SimpleNamespace(),
            "main": types.SimpleNamespace(clean_capitalize=lambda x: x),
            "bot": types.SimpleNamespace(InvalidTypeError=ValueError),
        }
        with patch.dict("sys.modules", mocked):
            spec = importlib.util.spec_from_file_location(
                "_silverhand_legacy_calculator_fixture", root / "src/calculator.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            calc = module.DamageCalculator("75mm", "Silverhand - Mk. IV (SvH)")
            self.assertEqual(calc.calculate_damage(), 1488)
            self.assertEqual(calc.general_damage_calculator(), 3)
            self.assertIn("It takes 3 75mm to kill a Silverhand", calc.get_kill_calculation())

    def test_reject_guesses_and_other_builds(self):
        self.assertIsNone(source_ref({"ObjectPath": "Other/DamageTypes/BPExplosive"}))
        self.assertIsNone(saved_enum("EDamageType::"))
        self.assertEqual(saved_enum("EDamageType::Explosive"), "Explosive")
        with self.assertRaises(ValueError):
            check(Path("/tmp"), self.weapon, self.target, self.damage, "99999999")


if __name__ == "__main__":
    unittest.main()
