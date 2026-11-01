"""Read-only coverage inventory tests; no private Foxhole exports required."""
import copy
import unittest

from scripts import report_weapon_identity_coverage as c


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.sheet = {
            "Ship 12.7mm (+20% HV)": {"Dev Name": "MGAmmo", "Damage": "82.5"},
            "Tank cannon": {"Dev Name": "LightTankAmmo", "Mount Dev Name": "TankCannonGunner", "Vehicle Dev Name": "TankC"},
            "Infantry weapon": {"Dev Name": "RifleAmmo", "Infantry Weapon Dev Name": "RifleW"},
            "Direct ammo": {"Dev Name": "GrenadeAmmo"},
        }
        self.overlay = {"Ship 12.7mm (+20% HV)": "Weapon:AssaultRifleHeavyW", "Tank cannon": "Mount:Unverified"}
        self.ledger = {"schema_version": 1, "records": [
            {"weapon_sheet_key": "Ship 12.7mm (+20% HV)", "scope": "Colonial Destroyer only"}
        ]}

    def test_scoped_candidate_not_promoted_to_generic_ship(self):
        out = c.inventory(self.sheet, self.overlay, self.ledger)
        self.assertEqual(out["counts"]["weapon_entries"], 4)
        self.assertEqual(out["counts"]["with_multiplier_overlay"], 2)
        self.assertEqual(out["counts"]["overlay_without_identity_hints"], 1)
        self.assertEqual(out["counts"]["with_scoped_reported_candidate"], 1)
        self.assertEqual(out["counts"]["verified_complete_asset_chains"], 0)
        candidate = out["items"][0]
        self.assertIn("scoped_reported", candidate["resolution_status"])
        self.assertFalse(candidate["can_generate_unattended"])

    def test_named_mount_is_hint_not_proof(self):
        out = c.inventory(self.sheet, self.overlay, self.ledger)
        tank = out["items"][1]
        self.assertEqual(tank["identity_hints_not_proof"]["Mount Dev Name"], "TankCannonGunner")
        self.assertEqual(tank["resolution_status"], "unverified_multiplier_mapping")
        self.assertFalse(tank["can_generate_unattended"])

    def test_missing_or_unknown_candidate_is_rejected(self):
        ledger = copy.deepcopy(self.ledger)
        ledger["records"][0]["weapon_sheet_key"] = "Missing"
        with self.assertRaisesRegex(ValueError, "unknown sheet key"):
            c.inventory(self.sheet, self.overlay, ledger)

    def test_unknown_overlay_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown sheet"):
            c.inventory(self.sheet, {"Deleted weapon": "Mount:Somewhere"}, self.ledger)

    def test_scoped_evidence_required(self):
        ledger = copy.deepcopy(self.ledger)
        ledger["records"][0]["scope"] = ""
        with self.assertRaisesRegex(ValueError, "scope must be explicit"):
            c.inventory(self.sheet, self.overlay, ledger)

    def test_missing_overlay_does_not_mean_verified(self):
        out = c.inventory(self.sheet, self.overlay, self.ledger)
        self.assertEqual(out["items"][-1]["resolution_status"], "no_curated_multiplier_not_verified")


if __name__ == "__main__":
    unittest.main()
