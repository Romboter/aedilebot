#!/usr/bin/env python3
"""Resolve explicitly saved VehicleSeatComponent MountComponent references to exact Blueprint class exports.

Source identity only. Numeric ObjectPath suffixes are never interpreted as an
export index. No runtime CDO inheritance or selected ammunition is assumed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from scripts.diff_blueprint_graph import checked
from scripts.find_blueprint_dependencies import asset_path
from scripts.resolve_blueprint_weapons import load
from scripts.triage_blueprint_inheritance_exceptions import exact_export


CLASS_NAME = re.compile(r"^BlueprintGeneratedClass'(?P<class_name>[A-Za-z_][A-Za-z0-9_]*_C)'$")


def resolve(root: Path, graph: dict, seat_report: dict):
    graph = checked(graph)
    if (seat_report.get("source_build_id") != graph["source_build_id"]
            or seat_report.get("relation_digest") != graph["relation_digest"]
            or seat_report.get("status") != "review_only_explicit_seat_mount_source_edges"
            or seat_report.get("safe_for_unattended_publication") is not False):
        raise ValueError("Unpinned seat source report")
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate indexed source package")
    root = root.resolve()
    source_edges = {}
    for edge in graph["object_references"]:
        if edge["field"] != "MountComponent":
            continue
        identity = (edge["source"], edge["record"])
        if identity in source_edges:
            raise ValueError("Duplicate indexed MountComponent edge")
        source_edges[identity] = edge
    cache = {}

    def exports(package):
        if package not in nodes:
            raise ValueError("Requested unindexed target package")
        if package not in cache:
            objs = load(exact_export(root, package, nodes[package]))
            if not isinstance(objs, list) or not all(isinstance(v, dict) for v in objs):
                raise ValueError("Invalid pinned export list")
            cache[package] = objs
        return cache[package]

    def lookup(side, seat_record):
        src = seat_record[side]
        seat_name = seat_record[side + "_component_export"]
        mount_ref = seat_record[side + "_mount_component"]
        if (seat_record[side + "_sha256"] != nodes.get(src)
                or mount_ref.get("package") != src
                or mount_ref.get("sha256") != nodes.get(src)
                or mount_ref.get("field") != seat_name + ".Properties.MountComponent"):
            raise ValueError("Seat mount source record provenance mismatch")
        status = mount_ref["status"]
        if status != "explicit_blueprint_target_exported":
            return {"status": "not_explicit_exported_mount_reference",
                    "source_status": status, "runtime_mount": "not_established"}
        path, raw_name, target = (mount_ref.get("saved_object_path"),
                                   mount_ref.get("saved_object_name"),
                                   mount_ref.get("target_package"))
        if (not isinstance(path, str) or asset_path(path) != target
                or target not in nodes or mount_ref.get("target_sha256") != nodes[target]):
            raise ValueError("Saved source MountComponent target identity mismatch")
        edge = source_edges.get((src, seat_name))
        if (edge is None or edge["object_path"] != path
                or edge["target"] != target or edge["status"] != "exported"
                or edge["source_sha256"] != nodes[src]):
            raise ValueError("MountComponent index edge is missing or changed")
        source_seats = [x for x in exports(src) if x.get("Name") == seat_name
                        and x.get("Type") == "VehicleSeatComponent"]
        if len(source_seats) != 1:
            raise ValueError("Changed exact saved seat export identity")
        source_ref = (source_seats[0].get("Properties") or {}).get("MountComponent")
        if (not isinstance(source_ref, dict)
                or source_ref.get("ObjectPath") != path
                or source_ref.get("ObjectName") != raw_name):
            raise ValueError("Source saved MountComponent differs from report")
        if not isinstance(raw_name, str):
            state, match = "missing_class_object_name", None
        else:
            match = CLASS_NAME.fullmatch(raw_name)
            state = "qualified_class_name_candidate" if match else "unsupported_class_object_name"
        if not match:
            return {"status": state, "target_package": target,
                    "target_sha256": nodes[target],
                    "runtime_mount": "not_established"}
        generated_class = match.group("class_name")
        objects = exports(target)
        candidates = [x for x in objects if x.get("Type") == "BlueprintGeneratedClass"
                      and x.get("Name") == generated_class]
        exact_default_name = "Default__" + generated_class
        default_candidates = [x for x in objects if x.get("Name") == exact_default_name]
        if len(candidates) == 1:
            state = "unique_saved_generated_class_export"
        elif len(candidates) > 1:
            state = "ambiguous_generated_class_export"
        else:
            state = "generated_class_not_exported"
        return {
            "status": state,
            "source_package": src, "source_sha256": nodes[src],
            "seat_export": seat_name, "field": "Properties.MountComponent",
            "original_object_path": path, "original_object_name": raw_name,
            "target_package": target, "target_sha256": nodes[target],
            "saved_generated_class": generated_class,
            "generated_class_matches": len(candidates),
            "exact_saved_default_name": exact_default_name,
            "exact_saved_default_matches": len(default_candidates),
            "selected_runtime_cdo": "not_established",
            "runtime_mount": "not_established",
        }

    rows, counters = [], Counter()
    for seat_record in seat_report["records"]:
        if (seat_record.get("effective_runtime_mount") != "not_established"
                or seat_record.get("effective_runtime_ammo") != "not_established"):
            raise ValueError("Source-only seat report promoted runtime fields")
        parent_result = lookup("parent", seat_record)
        child_result = lookup("child", seat_record)
        counters["source_pairs_checked"] += 1
        counters["parent_" + parent_result["status"]] += 1
        counters["child_" + child_result["status"]] += 1
        rows.append({
            "parent": seat_record["parent"], "child": seat_record["child"],
            "parent_sha256": seat_record["parent_sha256"],
            "child_sha256": seat_record["child_sha256"],
            "handler_record": seat_record["handler_record"],
            "record_index": seat_record["record_index"],
            "parent_scs_node": seat_record["parent_scs_node"],
            "parent_mount_target": parent_result,
            "child_mount_target": child_result,
            "effective_runtime_mount": "not_established",
            "effective_runtime_ammo": "not_established",
        })
    if len(rows) != seat_report.get("coverage", {}).get("counts", {}).get("verified_seat_source_pairs", 0):
        raise ValueError("Incomplete seat pair coverage")
    return {
        "schema_version": 1, "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "review_only_explicit_mount_generated_class_exports",
        "safe_for_unattended_publication": False,
        "coverage": {"counts": dict(sorted(counters.items()))},
        "records": rows,
        "limitations": [
            "Only explicitly saved mounted Blueprint class references are resolved; missing child references are never inherited.",
            "A saved generated class is not the selected runtime CDO, a mounted component instance, or selected ammo.",
            "No numeric ObjectPath suffix-to-export index assumption or gameplay damage calculation.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--seat-report", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = resolve(args.source_root,
                     json.loads(args.index.read_text(encoding="utf-8")),
                     json.loads(args.seat_report.read_text(encoding="utf-8")))
    out = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(out, encoding="utf-8")
    else:
        print(out, end="")


if __name__ == "__main__":
    main()
