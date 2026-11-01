#!/usr/bin/env python3
"""Resolve exported infantry pickup -> item component -> ammo and weapon rows.

Read-only research. Explicit ObjectPath and CodeName relationships only;
no string matching, numeric-proxy selection, production writes or auto-publish.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scripts.resolve_blueprint_weapons import explicit_property, load, sha256, table

PREFIX = "War/Content/Blueprints/"


def resolve_infantry(root: Path, pickup: Path, build_id: str, kinetic_factor: float = 1.25):
    root = root.resolve()
    pickup = (root / pickup).resolve()
    if not pickup.is_relative_to(root) or not pickup.is_file():
        raise ValueError("Pickup must be a JSON file inside export root")
    if not build_id.isdecimal():
        raise ValueError("Pinned numeric game build ID required")
    exports = load(pickup)
    if not isinstance(exports, list):
        raise ValueError("Malformed pickup export")
    defaults = [x for x in exports if str(x.get("Name", "")).startswith("Default__")]
    if len(defaults) != 1:
        raise ValueError("Expected exactly one pickup class default")
    props = defaults[0].get("Properties") or {}
    weapon_id = props.get("CodeName")
    comp = props.get("ItemComponentClass")
    reference = comp.get("ObjectPath") if isinstance(comp, dict) else None

    out = {
        "schema_version": 1,
        "game_build_id": build_id,
        "pickup_asset": pickup.relative_to(root).as_posix(),
        "source_sha256": sha256(pickup),
        "weapon_code_name": weapon_id,
        "status": "unresolved",
        "safe_for_unattended_publication": False,
        "evidence": [
            {"asset": pickup.relative_to(root).as_posix(),
             "property": "Default__/Properties/CodeName", "value": weapon_id},
            {"asset": pickup.relative_to(root).as_posix(),
             "property": "Default__/Properties/ItemComponentClass/ObjectPath",
             "value": reference}
        ],
    }
    if not isinstance(weapon_id, str) or not weapon_id:
        out["reason"] = "pickup_code_name_missing"
        return out
    if not isinstance(reference, str) or not reference.startswith(PREFIX):
        out["reason"] = "item_component_reference_not_exportable"
        return out
    component_path = root / (reference.removeprefix(PREFIX).split(".", 1)[0] + ".json")
    try:
        ammo_value, evidence = explicit_property(root, component_path,
                                                  ("CompatibleAmmoCodeName", "MultiAmmo"))
    except ValueError as exc:
        out["reason"] = "component_reference_unresolved"
        out["details"] = str(exc)
        return out
    if evidence:
        out["evidence"].append(evidence)
    if isinstance(ammo_value, str):
        options = [ammo_value]
    elif isinstance(ammo_value, dict) and isinstance(ammo_value.get("CompatibleAmmoNames"), list):
        options = ammo_value["CompatibleAmmoNames"]
    else:
        options = []
    if not options:
        out["reason"] = "component_compatible_ammo_not_found_in_exported_defaults"
        return out
    if any(not isinstance(x, str) or not x for x in options) or len(set(options)) != len(options):
        out["reason"] = "invalid_or_duplicate_ammunition_options"
        return out
    out["ammo_options"] = options
    if len(options) != 1:
        out["reason"] = "multiple_ammunition_options_require_explicit_variant_selection"
        return out
    ammo_id = options[0]
    out["ammo_code_name"] = ammo_id

    weapons, weapons_path = table(root, "BPWeaponDynamicData")
    ammos, ammos_path = table(root, "BPAmmoDynamicData")
    if weapon_id not in weapons or ammo_id not in ammos:
        out["reason"] = "named_weapon_or_ammo_row_absent"
        return out
    multiplier = weapons[weapon_id].get("DamageMultiplier")
    damage = ammos[ammo_id].get("Damage")
    dtype = (ammos[ammo_id].get("DamageType") or {}).get("ObjectName")
    valid = lambda v: isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) and v > 0
    if not valid(multiplier) or not valid(damage) or not isinstance(dtype, str):
        out["reason"] = "invalid_game_numeric_or_damage_type"
        return out
    factor = kinetic_factor if "Kinetic" in dtype or ammo_id == "AircraftAmmo" else 1.0
    if not valid(factor):
        raise ValueError("Invalid manual gameplay factor")
    out.update({
        "status": "resolved_with_manual_gameplay_rule" if factor != 1 else "resolved_from_exported_tables",
        "ammo_damage": damage, "weapon_multiplier": multiplier,
        "gameplay_factor": factor,
        "gameplay_factor_source": "reviewed_manual_rule_not_game_export" if factor != 1 else "not_applicable",
        "derived_direct_damage": damage * multiplier * factor,
        "table_evidence": [
            {"asset": weapons_path.relative_to(root).as_posix(), "sha256": sha256(weapons_path),
             "row": weapon_id, "field": "DamageMultiplier"},
            {"asset": ammos_path.relative_to(root).as_posix(), "sha256": sha256(ammos_path),
             "row": ammo_id, "field": "Damage"},
        ],
    })
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--pickup", type=Path, required=True, help="Relative ItemPickups/... JSON")
    p.add_argument("--build-id", required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    value = resolve_infantry(args.source_root, args.pickup, args.build_id)
    content = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
