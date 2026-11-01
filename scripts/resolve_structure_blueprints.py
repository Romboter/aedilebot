#!/usr/bin/env python3
"""Trace structure Blueprint identity and source-backed health/armour properties.

Never join structures by equal MaxHealth or display name. CodeName must come
from an explicit Blueprint default (possibly inherited) and match a named row
in BPStructureDynamicData. A missing ArmourType cannot be inferred from
native base class defaults; it remains an explicit gap for human review.
No bot sheet is read or written.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scripts.resolve_blueprint_weapons import explicit_property, load, sha256, table


def numeric_nonnegative(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def resolve_structure(root: Path, blueprint: Path, build_id: str) -> dict:
    root = root.resolve()
    path = (root / blueprint).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Structure must be an exported JSON file inside source root")
    if not build_id.isdecimal():
        raise ValueError("Pinned numeric game build ID required")
    result = {
        "schema_version": 1,
        "game_build_id": build_id,
        "blueprint": path.relative_to(root).as_posix(),
        "blueprint_sha256": sha256(path),
        "status": "review_only",
        "safe_for_unattended_publication": False,
        "health": {"status": "unresolved"},
        "armour": {"status": "unresolved"},
        "evidence": [],
    }
    if not isinstance(load(path), list):
        raise ValueError("Expected exported Blueprint object list")
    code, source = explicit_property(root, path, ("CodeName",))
    if source:
        result["evidence"].append({"role": "structure_identity", "value": code, **source})
    if not isinstance(code, str) or not code:
        result["health"]["reason"] = "structure_codename_missing"
        result["armour"]["reason"] = "structure_codename_missing"
        return result
    result["code_name"] = code
    rows, table_path = table(root, "BPStructureDynamicData")
    entry = rows.get(code)
    if not isinstance(entry, dict):
        result["health"]["reason"] = "named_structure_dynamic_row_missing"
        result["armour"]["reason"] = "named_structure_dynamic_row_missing"
        return result
    value = entry.get("MaxHealth")
    if not numeric_nonnegative(value):
        result["health"]["reason"] = "invalid_health_numeric"
        return result
    game_health, game_health_ref = explicit_property(root, path, ("MaxHealth",))
    if game_health_ref:
        result["evidence"].append({"role": "blueprint_health", "value": game_health, **game_health_ref})
    if game_health is not None and (not numeric_nonnegative(game_health) or not math.isclose(game_health, value, abs_tol=1e-6, rel_tol=1e-6)):
        result["health"] = {
            "status": "unresolved", "reason": "blueprint_and_dynamic_table_health_disagree",
            "table_health": value, "blueprint_health": game_health,
        }
    else:
        result["health"] = {
            "status": "named_dynamic_row_resolved",
            "max_health": value,
            "blueprint_health_checked": game_health is not None,
            "table_row_evidence": {"asset": table_path.relative_to(root).as_posix(),
                                   "sha256": sha256(table_path), "row": code, "field": "MaxHealth"},
        }
    armour, armour_source = explicit_property(root, path, ("ArmourType",))
    if armour_source:
        result["evidence"].append({"role": "armour_identity", "value": armour, **armour_source})
    if isinstance(armour, str) and armour.startswith("EArmourType::"):
        result["armour"] = {"status": "blueprint_explicit_or_inherited", "value": armour}
    else:
        result["armour"] = {
            "status": "unresolved",
            "reason": "armour_not_present_in_exported_blueprint_or_parents",
            "caution": "Do not equate missing exported ArmourType with NoArmour or a sheet value",
        }
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--structure", type=Path, required=True,
                   help="Structure Blueprint JSON path relative to source root")
    p.add_argument("--build-id", required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = resolve_structure(args.source_root, args.structure, args.build_id)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
