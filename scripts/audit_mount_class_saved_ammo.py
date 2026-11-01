#!/usr/bin/env python3
"""Audit saved ammunition declarations on exact vehicle-seat MountComponent class defaults.

This is a pinned source field inventory, NOT effective UE4.24 runtime CDO
reconstruction, mounted ammo selection, or damage calculation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.find_blueprint_dependencies import asset_path
from scripts.resolve_blueprint_weapons import load
from scripts.triage_blueprint_inheritance_exceptions import exact_export


AMMO_FIELDS = (
    "AmmoName", "CompatibleAmmoCodeName",
    "MultiAmmo", "GrenadeMultiAmmo", "WeaponConfigs",
)
REFERENCE_FIELDS = ("ProjectileClass", "ProjectileClasses", "ExplosionTemplate")


def describe(field, value):
    if field in ("AmmoName", "CompatibleAmmoCodeName"):
        if value == "None":
            return {"status": "saved_none_sentinel_candidate"}
        if isinstance(value, str) and value:
            return {"status": "explicit_saved_name", "saved_name": value}
        return {"status": "malformed_saved_name"}
    if field in ("MultiAmmo", "GrenadeMultiAmmo"):
        if not isinstance(value, dict):
            return {"status": "malformed_saved_struct"}
        out = {"saved_struct_fields": sorted(value)}
        if "CompatibleAmmoNames" not in value:
            return {"status": "saved_struct_without_names_array", **out}
        names = value["CompatibleAmmoNames"]
        if not isinstance(names, list):
            return {"status": "malformed_saved_names_array", **out}
        if not names:
            return {"status": "explicit_empty_saved_names_array",
                    "saved_names": [], **out}
        if any(not isinstance(name, str) or not name or name == "None" for name in names):
            return {"status": "invalid_saved_name_list", **out}
        return {"status": "explicit_saved_names_array", "saved_names": names, **out}
    if field == "WeaponConfigs":
        if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
            return {"status": "malformed_saved_configs"}
        return {"status": "explicit_saved_configs",
                "saved_config_count": len(value),
                "config_field_sets": [sorted(x) for x in value]}
    if field in REFERENCE_FIELDS:
        if field == "ProjectileClasses":
            if not isinstance(value, list):
                return {"status": "malformed_saved_reference_array"}
            return {"status": "explicit_saved_reference_array", "saved_count": len(value)}
        return {"status": "explicit_saved_reference" if isinstance(value, dict)
                else "unsupported_saved_reference_shape"}
    raise ValueError("Unsupported field " + field)


def audit(root: Path, graph: dict, class_report: dict):
    graph = checked(graph)
    if (class_report.get("source_build_id") != graph["source_build_id"]
            or class_report.get("relation_digest") != graph["relation_digest"]
            or class_report.get("status") != "review_only_explicit_mount_generated_class_exports"
            or class_report.get("safe_for_unattended_publication") is not False):
        raise ValueError("Unpinned mount class identity report")
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate source package")
    root = root.resolve()
    cache = {}

    def exports(package):
        if package not in nodes:
            raise ValueError("Unindexed class-default package")
        if package not in cache:
            objs = load(exact_export(root, package, nodes[package]))
            if not isinstance(objs, list) or not all(isinstance(v, dict) for v in objs):
                raise ValueError("Malformed pinned mount package")
            cache[package] = objs
        return cache[package]

    counts, fields, unique, rows = Counter(), Counter(), set(), []
    for pair in class_report["records"]:
        if (pair.get("effective_runtime_mount") != "not_established"
                or pair.get("effective_runtime_ammo") != "not_established"):
            raise ValueError("Runtime-effective mount state was promoted")
        for side in ("parent", "child"):
            mount = pair[side + "_mount_target"]
            if mount["status"] != "unique_saved_generated_class_export":
                counts[side + "_not_explicit_class"] += 1
                continue
            package = mount["target_package"]
            cls = mount["saved_generated_class"]
            if (mount["target_sha256"] != nodes.get(package)
                    or mount["selected_runtime_cdo"] != "not_established"):
                raise ValueError("Unpinned saved mount class")
            objects = exports(package)
            generated = [o for o in objects if o.get("Type") == "BlueprintGeneratedClass"
                         and o.get("Name") == cls]
            if len(generated) != 1:
                raise ValueError("Changed exact generated class")
            default_name = "Default__" + cls
            if mount["exact_saved_default_name"] != default_name:
                raise ValueError("Saved class-default identity diverged")
            defaults = [o for o in objects if o.get("Name") == default_name]
            if len(defaults) != mount["exact_saved_default_matches"]:
                raise ValueError("Saved class-default count diverged")
            if len(defaults) != 1:
                counts[side + "_class_default_missing_or_ambiguous"] += 1
                continue
            saved_props = defaults[0].get("Properties", {})
            if not isinstance(saved_props, dict):
                raise ValueError("Malformed saved class-default Properties")
            parent_ref = generated[0].get("SuperStruct")
            parent_path = parent_ref.get("ObjectPath") if isinstance(parent_ref, dict) else None
            saved = {}
            for field in AMMO_FIELDS + REFERENCE_FIELDS:
                item = (describe(field, saved_props[field]) if field in saved_props
                        else {"status": "not_serialized"})
                saved[field] = item
                fields[(side,field,item["status"])] += 1
            counts[side + "_verified_saved_class_defaults"] += 1
            unique.add((package,cls))
            rows.append({
                "side": side, "seat_parent": pair["parent"], "seat_child": pair["child"],
                "handler_record": pair["handler_record"], "record_index": pair["record_index"],
                "seat_source_key_proof": "saved_class_only",
                "mount_package": package, "mount_package_sha256": nodes[package],
                "generated_class": cls, "saved_default_export": default_name,
                "parent_blueprint_source_candidate": (
                    asset_path(parent_path) if isinstance(parent_path,str) else None),
                "saved_fields": saved,
                "effective_runtime_mount": "not_established",
                "effective_runtime_ammo": "not_established",
            })
    if (sum(v for k,v in counts.items() if k.endswith("_verified_saved_class_defaults")
            or k.endswith("_class_default_missing_or_ambiguous")
            or k.endswith("_not_explicit_class"))
            != 2*class_report.get("coverage",{}).get("counts",{}).get("source_pairs_checked",0)):
        raise ValueError("Partial mount class source coverage")
    return {
        "schema_version": 1, "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "review_only_mount_saved_ammunition_field_surface",
        "safe_for_unattended_publication": False,
        "coverage": {
            "counts": dict(sorted(counts.items())),
            "distinct_verified_mount_class_exports": len(unique),
            "field_status_counts": [
                {"side": side, "field": field, "status": status, "count": n}
                for (side,field,status), n in sorted(fields.items())
            ],
        },
        "records": rows,
        "limitations": [
            "Saved CDO fields are serialized source declarations, NOT effective UE4.24 runtime CDO defaults.",
            "An unsaved child field is not automatically inherited from a parent or selected at runtime.",
            "MultiAmmo partial structs and empty arrays are not merged with ancestor declarations.",
            "DataTable row presence, original field types, mount behavior and damage remain to be independently verified.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--mount-class-report", type=Path, required=True)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    result = audit(a.source_root,
                   json.loads(a.index.read_text(encoding="utf-8")),
                   json.loads(a.mount_class_report.read_text(encoding="utf-8")))
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if a.output:
        a.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
