#!/usr/bin/env python3
"""Resolve qualified serialized SCS component template names to exact exports.

Source-only: never assumes ObjectPath numeric .N means export index,
nor that a saved template is an effective runtime component.
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

QUALIFIED = re.compile(
    r"^(?P<component_type>[A-Za-z_][A-Za-z0-9_]*)'"
    r"(?P<class_name>[A-Za-z_][A-Za-z0-9_]*_C):"
    r"(?P<export_name>[A-Za-z_][A-Za-z0-9_]*)'$"
)


def inspect(root: Path, graph: dict, audit: dict):
    graph = checked(graph)
    if (audit.get("source_build_id") != graph["source_build_id"]
            or audit.get("relation_digest") != graph["relation_digest"]
            or audit.get("status") != "review_only_scs_component_template_export_inventory"
            or audit.get("safe_for_unattended_publication") is not False):
        raise ValueError("Unpinned component-template audit")
    root = root.resolve()
    nodes = {v["package"]: v["sha256"] for v in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate indexed package")
    cache = {}

    def exports(package):
        if package not in nodes:
            raise ValueError("Missing indexed package " + package)
        if package not in cache:
            obj = load(exact_export(root, package, nodes[package]))
            if not isinstance(obj, list) or not all(isinstance(x, dict) for x in obj):
                raise ValueError("Invalid exact package export " + package)
            cache[package] = obj
        return cache[package]

    counts = Counter()
    outer_shapes = Counter()
    result = []

    def match_ref(ref, package):
        if not isinstance(ref, dict):
            return {"status": "missing_reference"}
        if (ref.get("target_package") != package
                or asset_path(ref.get("object_path")) != package):
            raise ValueError("Unexpected component template target package")
        raw_name = ref.get("object_name")
        if not isinstance(raw_name, str):
            return {"status": "missing_qualified_object_name"}
        found = QUALIFIED.fullmatch(raw_name)
        if found is None:
            return {"status": "unsupported_qualified_object_name",
                    "object_name": raw_name}
        name, owner, kind = (found["export_name"],found["class_name"],
                             found["component_type"])
        objects = exports(package)
        generated_class = [x for x in objects if x.get("Type") == "BlueprintGeneratedClass"
                           and x.get("Name") == owner]
        component = [x for x in objects if x.get("Name") == name and x.get("Type") == kind]
        if len(generated_class) != 1:
            state = "generated_class_ambiguous" if len(generated_class)>1 else "generated_class_not_exported"
        elif len(component) != 1:
            state = "component_export_ambiguous" if len(component)>1 else "component_export_not_found"
        else:
            state = "qualified_source_export_unique"
        match = {
            "status": state, "package": package, "source_sha256": nodes[package],
            "component_type": kind, "generated_class": owner, "component_name": name,
            "generated_class_matches": len(generated_class),
            "component_matches": len(component),
            "original_object_path": ref["object_path"],
            "effective_runtime_component": "not_established",
        }
        if len(component) == 1:
            outer = component[0].get("Outer")
            outer_shapes["outer_object" if isinstance(outer,dict)
                         else "outer_absent" if outer is None else "outer_other"] += 1
            expected_name = "BlueprintGeneratedClass'" + owner + "'"
            observed_name = outer.get("ObjectName") if isinstance(outer,dict) else None
            observed_path = outer.get("ObjectPath") if isinstance(outer,dict) else None
            same_class = observed_name == expected_name
            same_package = asset_path(observed_path) == package if isinstance(observed_path,str) else False
            owner_state = ("serialized_outer_owner_match" if same_class and same_package else
                           "outer_reference_missing" if not isinstance(outer,dict) else
                           "outer_generated_class_mismatch")
            match["outer_source_provenance"] = {
                "status": owner_state, "expected_class": expected_name,
                "observed_class": observed_name, "observed_object_path": observed_path,
                "same_source_package": same_package,
                "runtime_owner": "not_established",
            }
            if state == "qualified_source_export_unique" and owner_state != "serialized_outer_owner_match":
                match["status"] = owner_state
        return match

    for row in audit.get("records", []):
        child, parent = row["child"], row["parent_package"]
        if (row["child_sha256"] != nodes.get(child)
                or row["parent_sha256"] != nodes.get(parent)
                or row.get("effective_runtime_component") != "not_established"):
            raise ValueError("Stale template source row")
        p = match_ref(row.get("parent_template_reference"), parent)
        c = match_ref(row.get("child_template_reference"), child)
        counts["parent_" + p["status"]] += 1
        counts["child_" + c["status"]] += 1
        result.append({
            "child": child, "child_sha256": nodes[child],
            "parent": parent, "parent_sha256": nodes[parent],
            "handler_record": row["handler_record"],
            "record_index": row["record_index"],
            "parent_scs_node": row["parent_scs_node"],
            "source_key_proof": row["source_key_proof"],
            "parent_component": p, "child_component": c,
            "effective_runtime_component": "not_established",
        })
    if len(result) != audit.get("coverage",{}).get("counts",{}).get("source_components_checked",0):
        raise ValueError("Component audit report coverage inconsistent")
    return {
        "schema_version": 1, "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "review_only_qualified_scs_template_source_exports",
        "safe_for_unattended_publication": False,
        "coverage": {"source_pairs": len(result), "status_counts": dict(sorted(counts.items())),
                     "component_outer_shapes": dict(sorted(outer_shapes.items()))},
        "records": result,
        "limitations": [
            "Qualified ObjectName syntax is matched only when all owner-class, export-name and component-type fields are exact.",
            "ObjectPath numeric suffix is not interpreted as a package export index.",
            "A unique source export does not establish effective CDO, component default merging, mounted gun, or damage.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--template-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = inspect(args.source_root, json.loads(args.index.read_text()),
                     json.loads(args.template_audit.read_text()))
    out = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(out)
    else:
        print(out, end="")


if __name__ == "__main__":
    main()
