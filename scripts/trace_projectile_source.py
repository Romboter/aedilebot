#!/usr/bin/env python3
"""Trace mounted projectile and explosion *references* without inventing damage.

An AmmoName may not correspond to a BPAmmoDynamicData row, while its
component also references an actual projectile class. Follow those exact
ObjectPaths and report where the source graph stops. ExplosionTemplate may
be a VFX asset, NOT proof of a gameplay damage number.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.find_blueprint_dependencies import asset_path
from scripts.resolve_blueprint_weapons import explicit_property, sha256, table


def trace(root: Path, mount_component: Path, game_build_id: str):
    root = root.resolve()
    mount = (root / mount_component).resolve()
    if not mount.is_relative_to(root) or not mount.is_file():
        raise ValueError("Mount component must be an exported JSON inside source root")
    if not game_build_id.isdecimal():
        raise ValueError("Numeric pinned game build ID required")

    result = {
        "schema_version": 1,
        "game_build_id": game_build_id,
        "mount_component": mount.relative_to(root).as_posix(),
        "status": "review_only_numeric_source_unresolved",
        "safe_for_unattended_publication": False,
        "evidence": [],
        "gaps": [],
    }
    def read_edge(source, field, role):
        value, location = explicit_property(root, source, (field,))
        if location:
            result["evidence"].append({"role": role, "value": value, **location})
        return value

    ammo_id = read_edge(mount, "AmmoName", "mount_ammo_name")
    result["declared_ammo_name"] = ammo_id
    projectile = read_edge(mount, "ProjectileClass", "mount_projectile_class")
    ref = projectile.get("ObjectPath") if isinstance(projectile, dict) else None
    package = asset_path(ref)
    if package is None:
        result["gaps"].append("explicit_projectile_class_not_exported")
        return result
    projectile_path = (root / (package + ".json")).resolve()
    if not projectile_path.is_relative_to(root) or not projectile_path.is_file():
        result["gaps"].append("referenced_projectile_package_not_exported")
        result["projectile_package"] = package
        return result
    result["projectile_package"] = package
    result["projectile_sha256"] = sha256(projectile_path)

    explosive = read_edge(projectile_path, "ExplosiveCodeName", "projectile_explosive_code")
    result["projectile_explosive_code"] = explosive
    if isinstance(ammo_id, str) and isinstance(explosive, str):
        result["ammunition_code_spelling"] = (
            "exact" if ammo_id == explosive else
            "case_only_difference" if ammo_id.casefold() == explosive.casefold() else
            "different_names_review_required"
        )

    explosion = read_edge(projectile_path, "ExplosionTemplate", "projectile_explosion_template")
    explosion_ref = explosion.get("ObjectPath") if isinstance(explosion, dict) else None
    explosion_package = asset_path(explosion_ref)
    if explosion_package:
        result["explosion_template_package"] = explosion_package
        path = (root / (explosion_package + ".json")).resolve()
        if path.is_relative_to(root) and path.is_file():
            result["explosion_template_sha256"] = sha256(path)
            # Retain the exact path; this does not demonstrate direct damage.
            result["gaps"].append("explosion_template_reference_is_not_numeric_damage_evidence")
        else:
            result["gaps"].append("explosion_template_package_not_exported")
    else:
        result["gaps"].append("projectile_explosion_template_not_exported")

    ammo, ammo_file = table(root, "BPAmmoDynamicData")
    result["ammo_table_evidence"] = {
        "asset": ammo_file.relative_to(root).as_posix(),
        "sha256": sha256(ammo_file),
        "exact_row_present": isinstance(ammo_id, str) and ammo_id in ammo,
    }
    if not isinstance(ammo_id, str) or ammo_id not in ammo:
        result["gaps"].append("declared_ammo_name_missing_from_dynamic_data")
    else:
        result["ammo_table_evidence"]["row"] = ammo_id
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--mount-component", type=Path, required=True)
    p.add_argument("--build-id", required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    value = trace(args.source_root, args.mount_component, args.build_id)
    data = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
