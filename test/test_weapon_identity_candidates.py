"""Synthetic verification of operator-reported mount identities, not proof of source assets."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import validate_weapon_identity_candidates as v


class DestroyerMachineGunIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = v.load_json(v.LEDGER)
        cls.sheet = v.load_json(v.SHEET)
        cls.overlay = v.load_json(v.OVERLAY)

    def test_reported_chain_is_explicitly_not_automated(self):
        result = v.validate(self.ledger, self.sheet, self.overlay)
        self.assertEqual(result["status"], "research_only_not_authorized_for_generation")
        record = result["results"][0]
        self.assertEqual(record["weapon"], "Ship 12.7mm (+20% HV)")
        self.assertTrue(record["current_overlay_is_unrelated_proxy"])
        self.assertIsNone(record["named_mount_row_matches"])
        self.assertFalse(record["asset_chain_independently_verified"])
        self.assertFalse(record["safe_for_automatic_updates"])

    def make_export(self, row_key, multiplier):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        path = root / v.TABLE
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps([{"Rows": {
            "AssaultRifleHeavyW": {"DamageMultiplier": 1.2},
            row_key: {"DamageMultiplier": multiplier}
        }}]), encoding="utf-8")
        return root

    def test_named_row_matching_is_not_complete_chain_verification(self):
        root = self.make_export("LargeShipDestroyerCMachineGunner", 1.2)
        result = v.validate(self.ledger, self.sheet, self.overlay, root)
        record = result["results"][0]
        self.assertTrue(record["named_mount_row_matches"])
        self.assertFalse(record["asset_chain_independently_verified"])

    def test_unrelated_numerical_match_must_not_be_used(self):
        root = self.make_export("WrongMount", 1.2)
        with self.assertRaisesRegex(ValueError, "named mount row absent"):
            v.validate(self.ledger, self.sheet, self.overlay, root)

    def test_changed_named_mount_must_fail_closed(self):
        root = self.make_export("LargeShipDestroyerCMachineGunner", 1.1)
        with self.assertRaisesRegex(ValueError, "multiplier changed"):
            v.validate(self.ledger, self.sheet, self.overlay, root)

    def test_claim_cannot_be_marked_verified_just_by_editing_status(self):
        ledger = copy.deepcopy(self.ledger)
        ledger["records"][0]["source_status"] = "verified"
        with self.assertRaisesRegex(ValueError, "cannot be promoted"):
            v.validate(ledger, self.sheet, self.overlay)

    def test_invalid_ammo_identity_fails(self):
        ledger = copy.deepcopy(self.ledger)
        ledger["records"][0]["inherited_ammo_dev_name"] = "OtherAmmo"
        with self.assertRaisesRegex(ValueError, "ammo ID disagrees"):
            v.validate(ledger, self.sheet, self.overlay)

    def test_seat_mount_cannot_differ_from_multiplier_row(self):
        ledger = copy.deepcopy(self.ledger)
        ledger["records"][0]["seat_mounts"][1]["value"] = "OtherMount"
        with self.assertRaisesRegex(ValueError, "inconsistent mount code"):
            v.validate(ledger, self.sheet, self.overlay)


if __name__ == "__main__":
    unittest.main()
