#!/usr/bin/env python3
"""Inventory current weapon-sheet identity hints without claiming asset verification.

This is a read-only triage report for Phase 4. A sheet's developer-name field
or a numerical multiplier proxy does not establish a Blueprint reference edge.
A scoped candidate does not validate a generic weapon entry for every vehicle.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELDS = (
    "Mount Dev Name",
    "Vehicle Dev Name",
    "Infantry Weapon Dev Name",
    "Emplacement Dev Name",
    "Tripod Dev Name",
)


def inventory(sheet: dict, overlay: dict, ledger: dict) -> dict:
    if not isinstance(sheet, dict) or not isinstance(overlay, dict):
        raise ValueError("Weapon sheet and overlay must be objects")
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1 or not isinstance(ledger.get("records"), list):
        raise ValueError("Invalid identity candidate ledger")
    candidates: dict[str, list[dict]] = {}
    for record in ledger["records"]:
        if not isinstance(record, dict) or not isinstance(record.get("weapon_sheet_key"), str):
            raise ValueError("Malformed candidate record")
        key = record["weapon_sheet_key"]
        if key not in sheet:
            raise ValueError("Candidate references unknown sheet key: " + key)
        if not isinstance(record.get("scope"), str) or not record["scope"].strip():
            raise ValueError("Candidate scope must be explicit: " + key)
        candidates.setdefault(key, []).append(record)
    unknown = sorted(set(overlay) - set(sheet))
    if unknown:
        raise ValueError("Overlay contains unknown sheet entries: " + ", ".join(unknown))
    details = []
    counts = Counter()
    for name, row in sheet.items():
        if not isinstance(row, dict):
            raise ValueError("Malformed weapon sheet entry: " + name)
        hint = {k: row[k] for k in FIELDS if isinstance(row.get(k), str) and row[k].strip()}
        c = candidates.get(name, [])
        has_overlay = name in overlay
        if c:
            status = "scoped_reported_blueprint_candidate_not_full_sheet_verification"
        elif has_overlay:
            status = "unverified_multiplier_mapping"
        else:
            status = "no_curated_multiplier_not_verified"
        counts["weapon_entries"] += 1
        counts["with_identity_hints"] += bool(hint)
        counts["without_identity_hints"] += not bool(hint)
        counts["with_multiplier_overlay"] += has_overlay
        counts["overlay_without_identity_hints"] += has_overlay and not bool(hint)
        counts["with_scoped_reported_candidate"] += bool(c)
        counts["verified_complete_asset_chains"] += 0
        for field in hint:
            counts["hint_" + field.replace(" ", "_").lower()] += 1
        details.append({
            "weapon": name,
            "ammo_dev_name_from_sheet": row.get("Dev Name"),
            "identity_hints_not_proof": hint,
            "uses_multiplier_overlay": has_overlay,
            "current_overlay_key_not_proof": overlay.get(name),
            "reported_candidate_scopes_not_approved": [x["scope"] for x in c],
            "resolution_status": status,
            "can_generate_unattended": False,
        })
    return {
        "schema_version": 1,
        "status": "identity_coverage_inventory_not_asset_verification",
        "counts": dict(sorted(counts.items())),
        "items": details,
        "limitations": [
            "Source DataTables and private Blueprint exports were not inspected.",
            "An explicit Dev Name field or a numerical match is not an asset-reference proof.",
            "No ship-wide, tank-wide or aircraft-wide coverage is asserted from a scoped candidate.",
            "No entry has been promoted to an independently verified complete asset chain.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--weapons", type=Path, default=ROOT / "data" / "Weapons.json")
    p.add_argument("--overlay", type=Path, default=ROOT / "data_manual" / "weapon_multipliers.json")
    p.add_argument("--candidates", type=Path, default=ROOT / "data_manual" / "weapon_asset_identity_candidates.json")
    p.add_argument("--output", type=Path, help="Optional JSON output path (review-only)")
    args = p.parse_args()
    try:
        report = inventory(
            json.loads(args.weapons.read_text(encoding="utf-8")),
            json.loads(args.overlay.read_text(encoding="utf-8")),
            json.loads(args.candidates.read_text(encoding="utf-8")),
        )
    except (ValueError, OSError, TypeError) as exc:
        p.exit(1, f"COVERAGE_FAILED: {exc}\n")
    rendered = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
