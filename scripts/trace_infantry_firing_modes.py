#!/usr/bin/env python3
"""Discover distinct infantry firing modes from explicit exported Blueprint fields.

Primary cartridge ammo and optional rifle-grenade modes must not be combined.
CompatibleAmmoNames and projectile class arrays are independent evidence:
matching array positions are NOT proof of a projectile-to-ammo association.
No secondary-mode damage multiplier is guessed, and publication is disabled.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scripts.find_blueprint_dependencies import asset_path
from scripts.resolve_blueprint_weapons import explicit_property, load, sha256, table
from scripts.resolve_infantry_weapons import resolve_infantry

PREFIX = "War/Content/Blueprints/"


def _ammo_options(value):
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, dict):
        value = value.get("CompatibleAmmoNames")
    if not isinstance(value, list):
        return None
    if not value or any(not isinstance(x, str) or not x for x in value) or len(value) != len(set(value)):
        return None
    return list(value)


def _classes(value, root):
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    result = []
    for index, ref in enumerate(value):
        objpath = ref.get("ObjectPath") if isinstance(ref, dict) else None
        pkg = asset_path(objpath)
        if not pkg:
            return None
        p = (root / (pkg + ".json")).resolve()
        if not p.is_relative_to(root):
            return None
        result.append({
            "index": index, "object_path": objpath, "package": pkg,
            "exported": p.is_file(), "export_sha256": sha256(p) if p.is_file() else None,
        })
    return result


def trace_firing_modes(root: Path, pickup: Path, build_id: str):
    root = root.resolve()
    pickup_path = (root / pickup).resolve()
    if not pickup_path.is_relative_to(root) or not pickup_path.is_file():
        raise ValueError("Pickup must be a JSON export inside the private source root")
    if not isinstance(build_id, str) or not build_id.isdecimal():
        raise ValueError("Pinned numeric game build ID required")

    # Preserve the existing primary-fire resolution, including its manual factor.
    primary = resolve_infantry(root, pickup, build_id)
    result = {
        "schema_version": 1,
        "game_build_id": build_id,
        "pickup_asset": pickup_path.relative_to(root).as_posix(),
        "pickup_sha256": sha256(pickup_path),
        "status": "review_only_no_generation",
        "safe_for_unattended_publication": False,
        "primary_fire": primary,
        "secondary_modes": [],
        "projectile_class_references": [],
        "limitations": [
            "Secondary ammunition and projectile arrays are not automatically paired by index.",
            "Primary BPWeaponDynamicData.DamageMultiplier is not assumed valid for grenade launches.",
            "Native-only firing mechanics are unresolved.",
        ],
    }
    records = load(pickup_path)
    defaults = [x for x in records if str(x.get("Name", "")).startswith("Default__")]
    if len(defaults) != 1:
        raise ValueError("Expected exactly one pickup class default")
    component = (defaults[0].get("Properties") or {}).get("ItemComponentClass")
    comp_path = component.get("ObjectPath") if isinstance(component, dict) else None
    package = asset_path(comp_path)
    if package is None:
        result["component_problem"] = "item_component_not_exportable"
        return result
    component_file = (root / (package + ".json")).resolve()
    if not component_file.is_relative_to(root) or not component_file.is_file():
        result["component_problem"] = "item_component_missing_from_export"
        return result
    result["item_component"] = {
        "object_path": comp_path, "package": package,
        "sha256": sha256(component_file),
    }

    ammo_rows, ammo_table = table(root, "BPAmmoDynamicData")
    for field, classes_field, label in (
        ("GrenadeMultiAmmo", "GrenadeClasses", "rifle_grenade_attachment"),
    ):
        ammo_value, ammo_edge = explicit_property(root, component_file, (field,))
        classes_value, classes_edge = explicit_property(root, component_file, (classes_field,))
        if ammo_edge is None and classes_edge is None:
            continue
        options = _ammo_options(ammo_value)
        projectiles = _classes(classes_value, root)
        mode = {
            "mode": label, "ammo_property": field,
            "ammo_evidence": ammo_edge, "projectile_property": classes_field,
            "projectile_evidence": classes_edge,
            "ammo_variants": [], "projectile_classes": projectiles or [],
            "status": "unresolved_mode_mapping", "safe_for_unattended_publication": False,
            "ammo_to_projectile_associations_verified": False,
            "damage_multiplier_source": None,
        }
        if options is None:
            mode["reason"] = "invalid_or_missing_explicit_ammo_options"
        else:
            for name in options:
                row = ammo_rows.get(name)
                if not isinstance(row, dict):
                    mode["ammo_variants"].append({
                        "ammo": name, "status": "named_ammo_row_missing",
                    })
                    continue
                damage = row.get("Damage")
                dtype = (row.get("DamageType") or {}).get("ObjectPath")
                good = (isinstance(damage, (int, float)) and not isinstance(damage, bool)
                        and math.isfinite(damage) and damage >= 0
                        and isinstance(dtype, str) and bool(dtype))
                mode["ammo_variants"].append({
                    "ammo": name, "status": "data_row_found" if good else "invalid_ammo_fields",
                    "raw_ammo_damage": damage if good else None,
                    "damage_type_object_path": dtype,
                    "table_evidence": {
                        "asset": ammo_table.relative_to(root).as_posix(),
                        "sha256": sha256(ammo_table),
                        "row": name,
                        "properties": ["Damage", "DamageType"],
                    },
                })
            if projectiles is None and classes_edge is not None:
                mode["reason"] = "invalid_projectile_class_references"
            elif any(x["status"] != "data_row_found" for x in mode["ammo_variants"]):
                mode["reason"] = "one_or_more_ammo_rows_unresolved"
            elif classes_edge is None:
                mode["reason"] = "projectile_class_relationship_not_exported"
            elif not projectiles or not all(x["exported"] for x in projectiles):
                mode["reason"] = "projectile_class_exports_missing"
            else:
                mode["reason"] = "ammo_to_projectile_and_multiplier_relationship_unverified"
        result["secondary_modes"].append(mode)

    # An infantry component can also reference projectile classes for its
    # primary-fire ammo (e.g. anti-tank launchers). Do not infer index mappings.
    for prop in ("ProjectileClasses",):
        value, location = explicit_property(root, component_file, (prop,))
        if location:
            resolved = _classes(value, root)
            result["projectile_class_references"].append({
                "property": prop, "evidence": location,
                "classes": resolved or [],
                "status": "explicit_references_only" if resolved is not None else "invalid_class_references",
                "ammo_associations_verified": False,
            })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pickup", type=Path, required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = trace_firing_modes(args.source_root, args.pickup, args.build_id)
    value = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(value, encoding="utf-8")
    else:
        print(value, end="")


if __name__ == "__main__":
    main()
