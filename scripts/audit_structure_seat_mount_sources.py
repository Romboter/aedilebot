#!/usr/bin/env python3
"""Audit explicit structure-seat mount source references without runtime inference.

All joins are exact, SHA-256 pinned, and source-only. This does not determine
which structure turret fires, how inherited templates are selected, or damage.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from scripts.diff_blueprint_graph import checked
from scripts.find_blueprint_dependencies import asset_path
from scripts.index_blueprint_graph import table_data
from scripts.resolve_blueprint_weapons import load
from scripts.triage_blueprint_inheritance_exceptions import exact_export

CLASS_NAME = re.compile(r"^BlueprintGeneratedClass'(?P<name>[A-Za-z_][A-Za-z0-9_]*_C)'$")


def audit(root: Path, graph: dict):
    graph = checked(graph)
    root = root.resolve()
    nodes = {x["package"]: x["sha256"] for x in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate indexed packages")
    table = table_data(root)["BPMountDynamicData"]
    expected = graph["table_exports"]["BPMountDynamicData"]
    if table["sha256"] != expected["sha256"] or table["rows"] is None:
        raise ValueError("Missing or changed mount table")
    rows = table["rows"]
    cache = {}

    def exports(package):
        if package not in nodes:
            raise ValueError("Unindexed package")
        if package not in cache:
            values = load(exact_export(root, package, nodes[package]))
            if not isinstance(values, list) or any(not isinstance(x, dict) for x in values):
                raise ValueError("Invalid source package exports")
            cache[package] = values
        return cache[package]

    def match_class(ref):
        if ref is None:
            return {"status": "explicit_null", "runtime_mount": "not_established"}
        if not isinstance(ref, dict):
            return {"status": "unsupported_reference_shape", "runtime_mount": "not_established"}
        object_path = ref.get("ObjectPath")
        object_name = ref.get("ObjectName")
        if not isinstance(object_path, str) or not object_path:
            return {"status": "missing_object_path", "runtime_mount": "not_established"}
        package = asset_path(object_path)
        if package is None:
            return {"status": "native_or_external_reference",
                    "saved_object_path": object_path, "runtime_mount": "not_established"}
        if package not in nodes:
            return {"status": "target_package_not_exported", "target_package": package,
                    "saved_object_path": object_path, "runtime_mount": "not_established"}
        out = {"target_package": package, "target_sha256": nodes[package],
               "saved_object_path": object_path, "saved_object_name": object_name,
               "runtime_mount": "not_established"}
        match = CLASS_NAME.fullmatch(object_name) if isinstance(object_name, str) else None
        if not match:
            return {**out, "status": "unsupported_generated_class_object_name"}
        exact_name = match.group("name")
        target = exports(package)
        matches = sum(x.get("Type") == "BlueprintGeneratedClass"
                      and x.get("Name") == exact_name for x in target)
        defaults = sum(x.get("Name") == "Default__" + exact_name for x in target)
        state = ("unique_saved_generated_class" if matches == 1 else
                 "no_matching_saved_class" if matches == 0 else
                 "ambiguous_saved_generated_class")
        return {**out, "status": state, "generated_class": exact_name,
                "generated_class_matches": matches,
                "saved_default_name": "Default__" + exact_name,
                "saved_default_matches": defaults}

    def match_mount_code(props):
        if "MountCodeName" not in props:
            return {"status": "not_serialized", "runtime_mount_code": "not_established"}
        name = props["MountCodeName"]
        result = {"saved_name": name, "table_sha256": expected["sha256"],
                  "source_original_property_type": "not_independently_inspected",
                  "runtime_mount_code": "not_established"}
        if not isinstance(name, str) or not name:
            return {**result, "status": "invalid_saved_name"}
        if name == "None":
            return {**result, "status": "none_sentinel_candidate"}
        if name in rows:
            return {**result, "status": "exact_saved_row_present"}
        return {**result, "status": "row_missing",
                "case_only_candidates_unverified": sorted(x for x in rows
                    if isinstance(x, str) and x != name and x.casefold() == name.casefold())}

    records, counts = [], Counter()
    for package in sorted(p for p in nodes if p.startswith("Structures/")):
        objects = exports(package)
        generated = {x.get("Name") for x in objects
                     if x.get("Type") == "BlueprintGeneratedClass"
                     and isinstance(x.get("Name"), str)}
        for obj in objects:
            if obj.get("Type") != "StructureSeatComponent":
                continue
            name = obj.get("Name")
            if not isinstance(name, str):
                raise ValueError("Unnamed structure seat component")
            props = obj.get("Properties") or {}
            if not isinstance(props, dict):
                raise ValueError("Malformed seat Properties")
            outer = obj.get("Outer")
            outer_path = outer.get("ObjectPath") if isinstance(outer, dict) else None
            outer_name = outer.get("ObjectName") if isinstance(outer, dict) else None
            owner_match = CLASS_NAME.fullmatch(outer_name) if isinstance(outer_name,str) else None
            owner = owner_match.group("name") if owner_match else None
            owner_status = ("saved_owner_class_and_outer_verified"
                            if asset_path(outer_path) == package and owner in generated else
                            "outer_owner_unresolved")
            code = match_mount_code(props)
            mount = (match_class(props["MountComponent"]) if "MountComponent" in props
                     else {"status": "not_serialized", "runtime_mount": "not_established"})
            counts["structure_seat_component_exports"] += 1
            counts["owner_" + owner_status] += 1
            counts["code_" + code["status"]] += 1
            counts["mount_" + mount["status"]] += 1
            records.append({
                "package": package, "source_sha256": nodes[package],
                "component_export": name, "component_type": "StructureSeatComponent",
                "saved_outer_owner_status": owner_status,
                "saved_outer_owner_class": owner,
                "mount_code": code, "mount_component": mount,
                "effective_runtime_seat": "not_established",
                "effective_runtime_mount": "not_established",
                "effective_runtime_ammo": "not_established",
            })
    return {
        "schema_version": 1, "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "review_only_structure_seat_mount_saved_source",
        "safe_for_unattended_publication": False,
        "mount_table_sha256": expected["sha256"],
        "coverage": dict(sorted(counts.items())),
        "records": records,
        "limitations": [
            "Explicit structure seats are source records; they may not be active or spawnable.",
            "No SCS node or inherited component override qualification has been performed.",
            "Saved owner Outer and target generated-class identities do not imply effective runtime mounting.",
            "MountCodeName row presence has no independent original tagged NameProperty proof here.",
            "No selection of ammo, turret firing behavior, mitigation or damage is inferred.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    result = audit(a.source_root, json.loads(a.index.read_text(encoding="utf-8")))
    rendered = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if a.output:
        a.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
