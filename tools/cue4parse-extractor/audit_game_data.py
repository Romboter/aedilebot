#!/usr/bin/env python3
"""Read-only AedileBot vs Foxhole DataTable audit. No sheet writes, no game asset uploads.

Supported comparisons: DTDamageProfiles mitigation fractions, BPVehicleDynamicData
and BPStructureDynamicData MaxHealth, and unmodified BPAmmoDynamicData weapon damage.
Mappings involving weapon/mount multipliers are deliberately NOT trusted (issue #44).
Bunker-tier identity mappings and native C++ armour types are not inferable here.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path


TABLES = ("DTDamageProfiles", "BPAmmoDynamicData", "BPVehicleDynamicData",
          "BPStructureDynamicData")
GAME_TABLE_DIR = Path("War/Content/Blueprints/Data")
KINETIC_FACTOR = Decimal("1.25")
EPSILON = Decimal("0.00001")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(stats_dir: Path, name: str) -> dict:
    path = stats_dir / GAME_TABLE_DIR / (name + ".json")
    data = read_json(path)
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise ValueError(f"{name} has an invalid export root")
    rows = data[0].get("Rows")
    if not isinstance(rows, dict) or not rows:
        raise ValueError(f"{name} has missing or empty Rows")
    return rows


def numeric(value) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def equal(a, b) -> bool:
    return abs(a - b) <= EPSILON


def section() -> dict:
    return {"matched": 0, "mismatched": 0, "unmapped": 0,
            "not_compared": 0, "details": []}


def add(section_result: dict, status: str, **detail):
    section_result[status] += 1
    if status != "matched":
        section_result["details"].append({"status": status, **detail})


def get_health(target: dict) -> Decimal | None:
    return numeric(target.get("Health"))


def audit(stats_dir: Path, data_dir: Path, overlay_path: Path,
          proposals_path: Path | None = None) -> dict:
    src = {name: table(stats_dir, name) for name in TABLES}
    sheets = {name: read_json(data_dir / (name + ".json"))
              for name in ("Damage", "Targets", "Weapons", "Bunker_piece")}
    overlay = read_json(overlay_path)
    proposals_doc = read_json(proposals_path) if proposals_path else {"proposals": {}}
    proposals = proposals_doc.get("proposals", {})
    if not isinstance(proposals, dict):
        raise ValueError("target proposals must map display names to developer names")
    for name, rows in sheets.items():
        if not isinstance(rows, dict):
            raise ValueError(f"{name}.json is not a JSON object")
    if not isinstance(overlay, dict):
        raise ValueError("weapon multiplier overlay is not a JSON object")

    result = {"schema_version": 1,
              "source_table_counts": {name: len(rows) for name, rows in src.items()},
              "sheet_counts": {name: len(rows) for name, rows in sheets.items()},
              "sections": {}}

    # Damage.json mitigation is a reduction FRACTION, not a damage multiplier.
    damage = section()
    extra_game_columns = set()
    for damage_name, sheet in sheets["Damage"].items():
        srcrow = src["DTDamageProfiles"].get(damage_name)
        if not isinstance(srcrow, dict):
            add(damage, "unmapped", name=damage_name, reason="damage profile absent")
            continue
        for key, value in sheet.items():
            if key in ("Name", "-", "ObjectType", "Nomitigation"):
                continue
            wanted = numeric(value)
            if wanted is None:
                continue
            actual = numeric(srcrow.get(key))
            if actual is None:
                add(damage, "unmapped", name=damage_name, field=key,
                    reason="numeric game value absent")
            elif equal(wanted, actual):
                add(damage, "matched")
            else:
                add(damage, "mismatched", name=damage_name, field=key,
                    sheet=str(wanted), game=str(actual))
        extra_game_columns.update(set(srcrow) - set(sheet))
    damage["manual_only_fields"] = ["Nomitigation"]
    damage["manual_only_cells"] = sum(
        "Nomitigation" in row for row in sheets["Damage"].values()
    )
    damage["source_only_fields"] = sorted(extra_game_columns)
    damage["source_only_profiles"] = sorted(set(src["DTDamageProfiles"]) - set(sheets["Damage"]))
    result["sections"]["damage_mitigation"] = damage

    vehicles = section()
    structures = section()
    unsupported_target_types = Counter()
    duplicate_devnames = Counter(row.get("Dev Name") for row in sheets["Targets"].values()
                                 if isinstance(row, dict) and row.get("Dev Name"))
    duplicate_devnames = {name: n for name, n in duplicate_devnames.items() if n > 1}
    for display_name, sheet in sheets["Targets"].items():
        objtype = sheet.get("ObjectType")
        if objtype == "Vehicles":
            dest, lookup = vehicles, src["BPVehicleDynamicData"]
        elif objtype == "Structures":
            dest, lookup = structures, src["BPStructureDynamicData"]
        else:
            unsupported_target_types[objtype or "(none)"] += 1
            continue
        dev = sheet.get("Dev Name")
        expected = get_health(sheet)
        actual_row = lookup.get(dev) if dev else None
        if not isinstance(actual_row, dict) or expected is None:
            add(dest, "unmapped", name=display_name, dev_name=dev or "",
                reason="source row or sheet health absent")
            continue
        actual = numeric(actual_row.get("MaxHealth"))
        if actual is None:
            add(dest, "unmapped", name=display_name, dev_name=dev,
                reason="game MaxHealth absent")
        elif equal(expected, actual):
            add(dest, "matched")
        else:
            proposal = {}
            suggested_dev = proposals.get(display_name)
            if suggested_dev:
                candidate_row = lookup.get(suggested_dev)
                candidate_health = numeric(candidate_row.get("MaxHealth")) if isinstance(candidate_row, dict) else None
                proposal = {
                    "proposed_dev_name": suggested_dev,
                    "proposed_health": str(candidate_health) if candidate_health is not None else None,
                    "proposal_matches_sheet": bool(candidate_health is not None and equal(expected, candidate_health)),
                    "proposal_requires_review": True,
                }
            add(dest, "mismatched", name=display_name, dev_name=dev,
                field="Health", sheet=str(expected), game=str(actual), **proposal)
    result["sections"]["vehicles_health"] = vehicles
    result["sections"]["structures_health"] = structures

    # For unmapped categories we explicitly do not infer a source table.
    result["unsupported_target_categories"] = dict(sorted(unsupported_target_types.items()))
    result["duplicate_target_dev_names"] = duplicate_devnames

    # The multiplier overlay may have numerical-proxy identities: issue #44.
    # Treat each such row as NOT VERIFIED regardless of apparent agreement.
    weapons = section()
    ammo = src["BPAmmoDynamicData"]
    for display_name, sheet in sheets["Weapons"].items():
        dev = sheet.get("Dev Name")
        source = ammo.get(dev) if dev else None
        if not isinstance(source, dict):
            add(weapons, "unmapped", name=display_name, dev_name=dev or "",
                reason="no matching ammo DataTable row")
            continue
        base = numeric(source.get("Damage"))
        listed = numeric(sheet.get("Damage"))
        if base is None or listed is None:
            add(weapons, "unmapped", name=display_name, dev_name=dev,
                reason="numeric damage missing")
            continue
        damage_type = source.get("DamageType", {})
        obj_name = str(damage_type.get("ObjectName", "")) if isinstance(damage_type, dict) else ""
        kinetic = "Kinetic" in obj_name or dev == "AircraftAmmo"
        expected = base * (KINETIC_FACTOR if kinetic else Decimal(1))
        if display_name in overlay:
            add(weapons, "not_compared", name=display_name, dev_name=dev,
                reason="weapon/mount identity not verified (issue #44)",
                overlay=str(overlay[display_name]))
        elif equal(listed, expected):
            add(weapons, "matched")
        else:
            add(weapons, "mismatched", name=display_name, dev_name=dev,
                field="Damage", sheet=str(listed), game_derived=str(expected),
                caveat="kinetic factor is a curated constant")
    result["sections"]["weapons_direct"] = weapons

    # Bunker tier parts cannot be joined to BPStructureDynamicData without
    # a verified game row identity mapping; never synthesize a tier join.
    bunker = section()
    for piece in sheets["Bunker_piece"]:
        add(bunker, "not_compared", name=piece,
            reason="tier-to-game-row mapping unverified")
    result["sections"]["bunker_tiers"] = bunker

    # Report is intentionally audit-only; human approval is required for updates.
    result["requires_human_review"] = any(
        v["mismatched"] or v["unmapped"] or v["not_compared"]
        for v in result["sections"].values()
    )
    return result


def markdown_report(report: dict) -> str:
    lines = ["# Foxhole DataTable audit (review only)", "",
             "No bot files were changed. No unverified multiplier or bunker mapping was inferred.",
             "", "| Comparison | Matched | Different | Unmapped | Not compared |",
             "|---|---:|---:|---:|---:|"]
    for name, sec in report["sections"].items():
        lines.append(f"| {name} | {sec['matched']} | {sec['mismatched']} | "
                     f"{sec['unmapped']} | {sec['not_compared']} |")
    lines += ["", "## Sample findings (up to 25 per category)", ""]
    for name, sec in report["sections"].items():
        lines.append(f"### {name}")
        mismatches = [item for item in sec["details"] if item["status"] == "mismatched"]
        if not sec["matched"] and not mismatches:
            lines.append("- No values verified in this category.")
        elif not mismatches:
            lines.append("- No numeric mismatches among compared values.")
        for item in mismatches[:25]:
            line = (f"- `{item['name']}` / `{item.get('field','')}`: "
                    f"sheet `{item['sheet']}` vs game-derived "
                    f"`{item.get('game', item.get('game_derived'))}`")
            if item.get("proposed_dev_name"):
                line += (f"; candidate `{item['proposed_dev_name']}` "
                         f"has game HP `{item['proposed_health']}` "
                         f"({'matches' if item['proposal_matches_sheet'] else 'DOES NOT match'} sheet; human review required)")
            lines.append(line)
        missing = [item for item in sec["details"] if item["status"] == "unmapped"]
        if missing:
            lines.append(f"- {len(missing)} unmapped: " +
                         ", ".join("`" + str(i["name"]) + "`" for i in missing[:12]) +
                         (" ..." if len(missing) > 12 else ""))
        if sec["not_compared"]:
            lines.append(f"- {sec['not_compared']} entries intentionally not compared.")
        lines.append("")
    lines += ["## Coverage limitations", "",
              f"- Damage includes {report['sections']['damage_mitigation']['manual_only_cells']} manual `Nomitigation` cells that are not in the game table."]
    for cat, count in report["unsupported_target_categories"].items():
        lines.append(f"- Target type `{cat}`: {count} entries not compared.")
    lines.append("- Weapon and mount multiplier identities are not verified (AedileBot #44).")
    lines.append("- Bunker tier mapping to source rows is not verified.")
    lines.append("- Armour types assigned in native game code cannot be validated here.")
    lines.append("- This comparison is not evidence of full actor/map fidelity.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target-proposals", type=Path, default=None)
    args = parser.parse_args()

    report = audit(args.stats, args.data, args.overlay, args.target_proposals)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = markdown_report(report)
    (args.output / "audit.md").write_text(md, encoding="utf-8")
    print(md)
    print("AUDIT_COMPLETE: read-only comparison; no data files modified.")


if __name__ == "__main__":
    main()
