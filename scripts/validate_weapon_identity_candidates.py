#!/usr/bin/env python3
"""Read-only checks of operator-reported weapon identity candidates.

This validates names against current bot sheets and optionally a *named*
BPMountDynamicData row. It CANNOT establish Blueprint inheritance or prove a
weapon-to-ammunition link. It never edits the multiplier overlay or bot data.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data_manual" / "weapon_asset_identity_candidates.json"
SHEET = ROOT / "data" / "Weapons.json"
OVERLAY = ROOT / "data_manual" / "weapon_multipliers.json"
TABLE = Path("War/Content/Blueprints/Data/BPMountDynamicData.json")
PENDING = "operator_reported_pending_pinned_export_review"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(ledger: dict, sheet: dict, overlay: dict, stats: Path | None = None) -> dict:
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1 or not isinstance(ledger.get("records"), list):
        raise ValueError("Unsupported identity-candidate schema")
    records = ledger["records"]
    if not records:
        raise ValueError("Identity-candidate list is empty")
    mount_rows = None
    if stats is not None:
        exports = load_json(stats / TABLE)
        if not isinstance(exports, list) or not exports or not isinstance(exports[0], dict) or not isinstance(exports[0].get("Rows"), dict):
            raise ValueError("Invalid BPMountDynamicData export")
        mount_rows = exports[0]["Rows"]

    result = []
    observed = set()
    for candidate in records:
        if not isinstance(candidate, dict):
            raise ValueError("Malformed identity-candidate record")
        name = candidate.get("weapon_sheet_key")
        if not isinstance(name, str) or not name or name in observed:
            raise ValueError("Invalid or duplicate weapon sheet key")
        observed.add(name)
        if candidate.get("source_status") != PENDING:
            raise ValueError(f"Candidate {name}: unreviewed metadata cannot be promoted to verified")
        if not isinstance(candidate.get("scope"), str) or not candidate["scope"].strip():
            raise ValueError(f"Candidate {name}: missing explicit applicability scope")
        if not isinstance(candidate.get("vehicle_blueprint"), str) or not candidate["vehicle_blueprint"]:
            raise ValueError(f"Candidate {name}: missing vehicle blueprint")
        if not isinstance(candidate.get("mount_component_blueprint"), str) or not candidate["mount_component_blueprint"]:
            raise ValueError(f"Candidate {name}: missing mount component")
        if not isinstance(candidate.get("inherited_component_class"), str) or not candidate["inherited_component_class"]:
            raise ValueError(f"Candidate {name}: missing inherited ammo component")
        if name not in sheet or sheet[name].get("Dev Name") != candidate.get("inherited_ammo_dev_name"):
            raise ValueError(f"Candidate {name}: ammo ID disagrees with Weapons.json")
        seats = candidate.get("seat_mounts")
        if not isinstance(seats, list) or not seats:
            raise ValueError(f"Candidate {name}: no seat mappings")
        for seat in seats:
            if not isinstance(seat, dict) or seat.get("property") != "MountCodeName" or seat.get("value") != candidate.get("mount_dynamic_data_row"):
                raise ValueError(f"Candidate {name}: inconsistent mount code")
        if candidate.get("mount_dynamic_data_table") != "BPMountDynamicData":
            raise ValueError(f"Candidate {name}: unsupported multiplier table")
        row_key = candidate.get("mount_dynamic_data_row")
        if not isinstance(row_key, str) or not row_key:
            raise ValueError(f"Candidate {name}: missing mount row")
        if candidate.get("proposed_asset_backed_reference") != "Mount:" + row_key:
            raise ValueError(f"Candidate {name}: proposed reference does not match named mount row")
        factor = candidate.get("reported_damage_multiplier")
        if isinstance(factor, bool) or not isinstance(factor, (int, float)) or not math.isfinite(factor) or factor <= 0:
            raise ValueError(f"Candidate {name}: invalid multiplier")
        row_match = None
        if mount_rows is not None:
            row = mount_rows.get(row_key)
            if not isinstance(row, dict):
                raise ValueError(f"Candidate {name}: named mount row absent from export")
            actual = row.get("DamageMultiplier")
            if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual):
                raise ValueError(f"Candidate {name}: invalid exported multiplier")
            row_match = math.isclose(actual, factor, rel_tol=1e-6, abs_tol=1e-8)
            if not row_match:
                raise ValueError(f"Candidate {name}: named mount multiplier changed (review required)")
        result.append({
            "weapon": name,
            "identity_status": "pending_source_chain_verification",
            "named_mount_row_checked": row_match is not None,
            "named_mount_row_matches": row_match,
            "current_overlay_is_unrelated_proxy": overlay.get(name) == candidate.get("current_unrelated_proxy"),
            "asset_chain_independently_verified": False,
            "safe_for_automatic_updates": False,
        })
    return {"schema_version": 1, "status": "research_only_not_authorized_for_generation", "results": result}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger", type=Path, default=LEDGER)
    p.add_argument("--weapons-json", type=Path, default=SHEET)
    p.add_argument("--overlay", type=Path, default=OVERLAY)
    p.add_argument("--stats", type=Path, help="Optional private game DataTable export root")
    args = p.parse_args(argv)
    try:
        report = validate(load_json(args.ledger), load_json(args.weapons_json),
                          load_json(args.overlay), args.stats)
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        print(f"IDENTITY_REVIEW_REQUIRED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
