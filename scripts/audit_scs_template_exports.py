#!/usr/bin/env python3
"""Audit exact serialized parent/child SCS component-template export references.

No implicit .N export-index or ObjectName interpretation is assumed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.find_blueprint_dependencies import asset_path
from scripts.resolve_scs_component_keys import resolve
from scripts.triage_blueprint_inheritance_exceptions import exact_export
from scripts.resolve_blueprint_weapons import load


def inspect(root: Path, graph: dict, base: dict, typed: dict):
    graph = checked(graph)
    if (base.get("source_build_id") != graph["source_build_id"]
        or base.get("relation_digest") != graph["relation_digest"]
        or base.get("safe_for_unattended_publication") is not False
        or base.get("status") != "review_only_serialized_scs_key_matches"):
        raise ValueError("Unpinned SCS matcher input")
    if (typed.get("source_build_id") != graph["source_build_id"]
        or typed.get("relation_digest") != graph["relation_digest"]
        or typed.get("safe_for_unattended_publication") is not False
        or typed.get("status") != "review_only_type_gated_scs_case_identity"):
        raise ValueError("Unpinned typed source identity input")
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate indexed source packages")
    cache = {}
    root = root.resolve()

    def exports(package):
        if package not in nodes:
            raise ValueError("Missing indexed package: " + str(package))
        if package not in cache:
            data = load(exact_export(root, package, nodes[package]))
            if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
                raise ValueError("Malformed checked export: " + package)
            cache[package] = data
        return cache[package]

    overlay = {}
    for entry in typed.get("reviewed_candidates", []):
        key = (entry["child"], entry["record_index"])
        if key in overlay:
            raise ValueError("Duplicate typed source identity")
        overlay[key] = entry
    out, counts, shapes = [], Counter(), Counter()
    used_typed = set()

    def reference(ref, expected_package):
        if not isinstance(ref, dict):
            return {"status": "missing_or_non_object_reference"}
        path = ref.get("ObjectPath")
        objname = ref.get("ObjectName")
        if not isinstance(path, str):
            return {"status": "missing_object_path", "object_name": objname}
        package = asset_path(path)
        if package != expected_package:
            return {"status": "target_package_mismatch",
                    "expected_package": expected_package, "target_package": package}
        if not isinstance(objname, str) or not objname:
            return {"status": "missing_object_name", "target_package": package,
                    "object_path": path}
        matching_name = [x for x in exports(package) if x.get("Name") == objname]
        # No guessed .N -> export index, no suffix matching, no inferred object Class.
        return {"status": "object_name_exact_export" if len(matching_name)==1
                else "object_name_ambiguous" if len(matching_name)>1
                else "object_name_not_export_name",
                "target_package": package, "object_path": path,
                "object_name": objname, "exact_name_matches": len(matching_name),
                "object_name_examples": [x.get("Name") for x in exports(package)[:2]]}

    for row in base.get("records", []):
        child = row["child"]
        key = (child, row["record_index"])
        parent = row.get("parent_scs_match")
        if row["status"] == "unique_serialized_key_match":
            if key in overlay:
                raise ValueError("Typed overlay unexpectedly claims exact row")
            if not parent:
                raise ValueError("Exact source key lacks parent node")
            owner_package, node_name = parent["parent_package"], parent["scs_node_record"]
        else:
            proof = overlay.get(key)
            if not proof or proof.get("status") != "verified_typed_fname_case_only_source_identity":
                counts["unresolved_source_key"] += 1
                continue
            used_typed.add(key)
            owner_package, node_name = proof["parent_package"], proof["parent_scs_node"]
        if (owner_package not in nodes or
            row.get("owner_class", {}).get("target_package") != owner_package):
            raise ValueError("Parent owner package mismatch")
        if row.get("source_sha256") != nodes.get(child):
            raise ValueError("Stale child package hash")
        source_nodes = [x for x in exports(owner_package)
                        if x.get("Type") == "SCS_Node" and x.get("Name") == node_name]
        if len(source_nodes) != 1:
            raise ValueError("Parent SCS node identity not unique")
        parent_ref = (source_nodes[0].get("Properties") or {}).get("ComponentTemplate")
        source_handlers = [x for x in exports(child)
                           if x.get("Type") == "InheritableComponentHandler"
                           and x.get("Name") == row["handler_record"]]
        if len(source_handlers) != 1:
            raise ValueError("Source child handler record not unique")
        source_records = (source_handlers[0].get("Properties") or {}).get("Records")
        i = row["record_index"]
        if not isinstance(source_records, list) or i >= len(source_records) or not isinstance(source_records[i], dict):
            raise ValueError("Indexed child handler record missing")
        child_ref = source_records[i].get("ComponentTemplate")
        indexed_child_ref = row.get("child_template")
        if indexed_child_ref:
            if (not isinstance(child_ref, dict)
                or child_ref.get("ObjectPath") != indexed_child_ref["object_path"]
                or indexed_child_ref["target_package"] != child):
                raise ValueError("Child component reference changed from indexed edge")
        parent_info = reference(parent_ref, owner_package)
        child_info = reference(child_ref, child)
        counts["source_components_checked"] += 1
        counts["parent_" + parent_info["status"]] += 1
        counts["child_" + child_info["status"]] += 1
        for kind, data in (("parent",parent_info),("child",child_info)):
            if "object_name" in data:
                shapes[kind + "_object_name_apostrophe"] += int("'" in str(data["object_name"]))
            if "object_path" in data:
                shapes[kind + "_object_path_dot_suffix"] += int(
                    str(data["object_path"]).rsplit(".",1)[-1].isdigit())
        out.append({
            "child": child, "child_sha256": nodes[child],
            "handler_record": row["handler_record"],
            "record_index": row["record_index"],
            "source_key_proof": "typed_fname_case_only" if key in used_typed else "exact",
            "parent_package": owner_package,
            "parent_sha256": nodes[owner_package],
            "parent_scs_node": node_name,
            "parent_template_reference": parent_info,
            "child_template_reference": child_info,
            "effective_runtime_component": "not_established",
        })
    if used_typed != set(overlay):
        raise ValueError("Typed source evidence not fully used")
    return {
        "schema_version": 1, "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "review_only_scs_component_template_export_inventory",
        "safe_for_unattended_publication": False,
        "coverage": {"counts": dict(sorted(counts.items())),
                     "reference_shape_counts": dict(sorted(shapes.items()))},
        "records": out,
        "limitations": [
            "ObjectPath numeric suffix and ObjectName semantics are not assumed.",
            "An exact exported-name match is only a source observation, not engine runtime object identity.",
            "A missing full export does not imply a missing runtime template.",
            "No component default merging, gun/ammo identity, or damage.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--matching-report", type=Path, required=True)
    p.add_argument("--typed-report", type=Path, required=True)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    report = inspect(a.source_root, json.loads(a.index.read_text()),
                     json.loads(a.matching_report.read_text()),
                     json.loads(a.typed_report.read_text()))
    serialized = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if a.output:
        a.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
