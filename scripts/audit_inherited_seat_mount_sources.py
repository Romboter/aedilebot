#!/usr/bin/env python3
"""Trace explicit saved VehicleSeatComponent mount fields from verified SCS pairs.

No field is inherited from parent to child. A saved MountCodeName matching an
exported row is a serialized source identity, not an effective weapon or damage.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.find_blueprint_dependencies import asset_path
from scripts.index_blueprint_graph import canonical, check_name, table_data
from scripts.resolve_blueprint_weapons import load
from scripts.triage_blueprint_inheritance_exceptions import exact_export


def analyze(root: Path, graph: dict, qualified: dict):
    graph = checked(graph)
    if (qualified.get("source_build_id") != graph["source_build_id"]
            or qualified.get("relation_digest") != graph["relation_digest"]
            or qualified.get("status") != "review_only_qualified_scs_template_source_exports"
            or qualified.get("safe_for_unattended_publication") is not False):
        raise ValueError("Unpinned qualified SCS component identity report")
    root = root.resolve()
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate indexed packages")
    tables = table_data(root)
    named_table = "BPMountDynamicData"
    expected_table = graph["table_exports"][named_table]
    if (not expected_table["available"]
            or not tables[named_table]["rows"]
            and tables[named_table]["rows"] is None
            or tables[named_table]["sha256"] != expected_table["sha256"]):
        raise ValueError("Pinned mount DataTable missing or changed")
    table_rows = tables[named_table]["rows"]
    table_sha = expected_table["sha256"]
    row_edges = {}
    for edge in graph["numeric_row_references"]:
        if edge["field"] != "MountCodeName" or edge["table"] != named_table:
            continue
        key = (edge["source"], edge["record"])
        if key in row_edges:
            raise ValueError("Duplicate indexed seat mount row reference")
        row_edges[key] = edge
    object_edges = {}
    for edge in graph["object_references"]:
        if edge["field"] != "MountComponent":
            continue
        key = (edge["source"], edge["record"])
        if key in object_edges:
            raise ValueError("Duplicate indexed seat MountComponent edge")
        object_edges[key] = edge
    cache = {}

    def exports(package):
        if package not in nodes:
            raise ValueError("Unknown indexed seat package")
        if package not in cache:
            data = load(exact_export(root, package, nodes[package]))
            if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
                raise ValueError("Invalid pinned package exports")
            cache[package] = data
        return cache[package]

    def seat(package, component):
        if (component.get("status") != "qualified_source_export_unique"
                or component.get("component_type") != "VehicleSeatComponent"
                or component.get("package") != package
                or component.get("source_sha256") != nodes.get(package)
                or component.get("outer_source_provenance", {}).get("status")
                != "serialized_outer_owner_match"):
            raise ValueError("Unverified VehicleSeatComponent export")
        candidates = [x for x in exports(package)
                      if x.get("Name") == component["component_name"]
                      and x.get("Type") == "VehicleSeatComponent"]
        owners = [x for x in exports(package)
                  if x.get("Name") == component["generated_class"]
                  and x.get("Type") == "BlueprintGeneratedClass"]
        if len(candidates) != 1 or len(owners) != 1:
            raise ValueError("Ambiguous or changed seat export")
        obj = candidates[0]
        outer = obj.get("Outer")
        if (not isinstance(outer, dict)
                or outer.get("ObjectName") != "BlueprintGeneratedClass'" +
                component["generated_class"] + "'"
                or asset_path(outer.get("ObjectPath")) != package):
            raise ValueError("Seat Outer ownership drifted")
        props = obj.get("Properties", {})
        if not isinstance(props, dict):
            raise ValueError("Malformed seat Properties")
        return props

    counts = Counter()
    field_counts = Counter()
    rows = []

    def mount_code(package, record, props):
        origin = {"package": package, "sha256": nodes[package],
                  "field": record + ".Properties.MountCodeName"}
        if "MountCodeName" not in props:
            if (package, record) in row_edges:
                raise ValueError("Index has missing saved mount field")
            return {**origin, "status": "not_serialized"}
        raw = props["MountCodeName"]
        indexed = row_edges.get((package, record))
        if indexed is None or indexed["source_sha256"] != nodes[package] or (
            indexed["row"] != raw or indexed["table_sha256"] != table_sha):
            raise ValueError("Mount row edge diverged from saved seat or table")
        status = indexed["status"]
        expected = ("none_sentinel_candidate" if raw == "None" else
                    "invalid_identifier" if not check_name(raw) else
                    "row_present" if raw in table_rows else "row_missing")
        if status != expected:
            raise ValueError("Indexed MountCodeName status not consistent with pinned DataTable")
        if status == "row_missing":
            possible = sorted(k for k in table_rows if isinstance(k, str) and
                              k != raw and k.casefold() == raw.casefold())
            if indexed["case_only_spelling_candidates_unverified"] != possible:
                raise ValueError("Stale case-only candidate evidence")
        else:
            possible = []
        return {
            **origin, "status": status,
            "saved_value": raw,
            "table": named_table, "table_sha256": table_sha,
            "exact_row_identity_from_saved_field": status == "row_present",
            "case_only_row_candidates_unverified": possible,
            "original_name_property_type": "not_independently_verified",
            "effective_mount_name": "not_established",
        }

    def mount_component(package, record, props):
        origin = {"package": package, "sha256": nodes[package],
                  "field": record + ".Properties.MountComponent"}
        if "MountComponent" not in props:
            if (package, record) in object_edges:
                raise ValueError("Index has missing saved mount object field")
            return {**origin, "status": "not_serialized"}
        raw = props["MountComponent"]
        if raw is None:
            if (package, record) in object_edges:
                raise ValueError("Index has unexpected null MountComponent edge")
            return {**origin, "status": "explicit_null"}
        if not isinstance(raw, dict):
            if (package, record) in object_edges:
                raise ValueError("Index has malformed MountComponent edge")
            return {**origin, "status": "unsupported_saved_reference_shape"}
        path = raw.get("ObjectPath")
        if not isinstance(path, str) or not path:
            if (package, record) in object_edges:
                raise ValueError("Index has missing ObjectPath")
            return {**origin, "status": "object_path_missing"}
        target = asset_path(path)
        indexed = object_edges.get((package, record))
        if target is None:
            if indexed:
                raise ValueError("Indexed Blueprint edge for native target")
            return {**origin, "status": "native_or_external_target",
                    "saved_object_path": path, "saved_object_name": raw.get("ObjectName")}
        if (not indexed or indexed["source_sha256"] != nodes[package]
                or indexed["object_path"] != path or indexed["target"] != target
                or indexed["status"] !=
                ("exported" if target in nodes else "missing_export")):
            raise ValueError("Saved MountComponent disagrees with indexed Blueprint edge")
        return {
            **origin,
            "status": "explicit_blueprint_target_" + indexed["status"],
            "saved_object_path": path,
            "saved_object_name": raw.get("ObjectName"),
            "target_package": target,
            "target_sha256": nodes.get(target),
            "exact_target_export": "not_established",
            "effective_mount_component": "not_established",
        }

    def comparison(parent, child, key):
        p_has = key in parent
        c_has = key in child
        if not p_has and not c_has:
            return "neither_serialized"
        if not p_has:
            return "child_only_serialized"
        if not c_has:
            return "parent_only_serialized"
        return ("both_serialized_same" if canonical(parent[key]) == canonical(child[key])
                else "both_serialized_changed")

    for record in qualified.get("records", []):
        parent, child = record["parent"], record["child"]
        pc, cc = record["parent_component"], record["child_component"]
        if (record.get("parent_sha256") != nodes.get(parent)
                or record.get("child_sha256") != nodes.get(child)
                or record.get("effective_runtime_component") != "not_established"):
            raise ValueError("Changed SCS record provenance")
        if pc.get("component_type") != "VehicleSeatComponent" or cc.get("component_type") != "VehicleSeatComponent":
            counts["non_seat_pair_excluded"] += 1
            continue
        pprops, cprops = seat(parent, pc), seat(child, cc)
        p_name, c_name = pc["component_name"], cc["component_name"]
        data = {
            "parent": parent, "parent_sha256": nodes[parent],
            "child": child, "child_sha256": nodes[child],
            "parent_component_export": p_name,
            "child_component_export": c_name,
            "parent_scs_node": record["parent_scs_node"],
            "handler_record": record["handler_record"],
            "record_index": record["record_index"],
            "source_key_proof": record["source_key_proof"],
            "parent_mount_code": mount_code(parent, p_name, pprops),
            "child_mount_code": mount_code(child, c_name, cprops),
            "parent_mount_component": mount_component(parent, p_name, pprops),
            "child_mount_component": mount_component(child, c_name, cprops),
            "mount_code_comparison": comparison(pprops, cprops, "MountCodeName"),
            "mount_component_comparison": comparison(pprops, cprops, "MountComponent"),
            "effective_runtime_mount": "not_established",
            "effective_runtime_ammo": "not_established",
        }
        rows.append(data)
        counts["verified_seat_source_pairs"] += 1
        for field in ("mount_code", "mount_component"):
            field_counts[(field, "comparison", data[field + "_comparison"])] += 1
            for side in ("parent", "child"):
                field_counts[(field, side, data[side + "_" + field]["status"])] += 1
    if counts["verified_seat_source_pairs"] + counts["non_seat_pair_excluded"] != qualified["coverage"]["source_pairs"]:
        raise ValueError("Partial SCS seat pair coverage")
    return {
        "schema_version": 1, "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "review_only_explicit_seat_mount_source_edges",
        "safe_for_unattended_publication": False,
        "mount_table_sha256": table_sha,
        "coverage": {
            "counts": dict(sorted(counts.items())),
            "field_status_counts": [
                {"field": f, "scope": scope, "status": status, "count": n}
                for (f, scope, status), n in sorted(field_counts.items())
            ],
        },
        "records": rows,
        "limitations": [
            "Only separately saved mount code and component references are inventoried; absent fields are not inherited.",
            "MountCodeName row presence proves a source row identifier, not a runtime weapon selection or FName tag.",
            "A MountComponent target package is not proof of the exact target export or selected ammo.",
            "No UE4.24 component CDO reconstruction, runtime mount, ammunition selection or damage.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--qualified-exports", type=Path, required=True)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    report = analyze(a.source_root, json.loads(a.index.read_text()),
                     json.loads(a.qualified_exports.read_text()))
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if a.output:
        a.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
