#!/usr/bin/env python3
"""Review-only serialized SCS component-key shape inventory.

Inspects exact, SHA-checked exports behind handler owner/template pairs.
Does NOT assert a runtime component override or choose effective CDO values.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.pair_inheritable_component_records import pair_records
from scripts.triage_blueprint_inheritance_exceptions import exact_export
from scripts.resolve_blueprint_weapons import load


def shape(value):
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "object:" + ",".join(sorted(value))
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "bool"
    return type(value).__name__


def inspect(root: Path, graph: dict):
    graph = checked(graph)
    root = root.resolve()
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    pairs = pair_records(graph)["records"]
    package_cache = {}

    def exports(package):
        if package not in nodes:
            raise ValueError("Unexported package: " + package)
        if package not in package_cache:
            package_cache[package] = load(exact_export(root, package, nodes[package]))
        return package_cache[package]

    counts = Counter()
    key_fields = Counter()
    key_shapes = Counter()
    owner_node_fields = Counter()
    owner_node_shapes = Counter()
    examples = []
    for item in pairs:
        package = item["source_package"]
        handler_name = item["source_record"]
        handlers = [o for o in exports(package)
                    if o.get("Type") == "InheritableComponentHandler"
                    and o.get("Name") == handler_name]
        if len(handlers) != 1:
            raise ValueError("Ambiguous source handler: " + package)
        records = (handlers[0].get("Properties") or {}).get("Records")
        i = item["record_index"]
        if not isinstance(records, list) or i >= len(records) or not isinstance(records[i], dict):
            raise ValueError("Handler indexed record absent or malformed: " + package)
        entry = records[i]
        key = entry.get("ComponentKey")
        if not isinstance(key, dict):
            raise ValueError("Handler key absent or malformed: " + package)
        owner = item["owner_class"]
        template = item["component_template"]
        if owner and key.get("OwnerClass", {}).get("ObjectPath") != owner["object_path"]:
            raise ValueError("Handler owner path diverges from index: " + package)
        if template and entry.get("ComponentTemplate", {}).get("ObjectPath") != template["object_path"]:
            raise ValueError("Handler template path diverges from index: " + package)
        for field, value in key.items():
            key_fields[field] += 1
            key_shapes[(field, shape(value))] += 1
        if not owner:
            counts["owner_not_blueprint"] += 1
            continue
        owner_package = owner["target_package"]
        candidate_nodes = [o for o in exports(owner_package) if o.get("Type") == "SCS_Node"]
        counts["source_pairs_checked"] += 1
        counts["owner_scs_nodes_total"] += len(candidate_nodes)
        for node in candidate_nodes:
            props = node.get("Properties") or {}
            if not isinstance(props, dict):
                raise ValueError("Malformed source node properties: " + owner_package)
            for field, value in props.items():
                owner_node_fields[field] += 1
                owner_node_shapes[(field, shape(value))] += 1
        name = key.get("SCSVariableName")
        if isinstance(name, str) and name and name != "None":
            counts["key_name_present"] += 1
            same_name = [n for n in candidate_nodes
                         if (n.get("Properties") or {}).get("VariableName") == name]
            if len(same_name) == 1:
                counts["same_name_node_unique_candidate"] += 1
            elif len(same_name) > 1:
                counts["same_name_node_ambiguous"] += 1
            else:
                counts["same_name_node_not_found"] += 1
        else:
            counts["key_name_absent_or_non_string"] += 1
        if len(examples) < 12:
            examples.append({
                "child": package,
                "owner": owner_package,
                "key_fields": {k: shape(v) for k, v in sorted(key.items())},
                "key_variable_name": name if isinstance(name, str) else None,
                "owner_scs_node_count": len(candidate_nodes),
                "owner_scs_node_properties": [
                    {"name": n.get("Name"),
                     "variable_name": (n.get("Properties") or {}).get("VariableName"),
                     "variable_guid_shape": shape((n.get("Properties") or {}).get("VariableGuid"))}
                    for n in candidate_nodes[:4]],
            })
    return {
        "source_build_id": graph["source_build_id"],
        "source_relation_digest": graph["relation_digest"],
        "status": "review_only_scs_key_shape_diagnostic",
        "safe_for_unattended_publication": False,
        "counts": dict(sorted(counts.items())),
        "handler_key_field_counts": dict(sorted(key_fields.items())),
        "handler_key_shape_counts": [
            {"field": field, "shape": pattern, "count": count}
            for (field, pattern), count in sorted(key_shapes.items())],
        "owner_scs_node_field_counts": dict(sorted(owner_node_fields.items())),
        "owner_scs_node_shape_counts": [
            {"field": field, "shape": pattern, "count": count}
            for (field, pattern), count in sorted(owner_node_shapes.items())],
        "bounded_examples": examples,
        "limitations": [
            "Only serialized JSON shapes, not original UE4 PropertyTag types.",
            "Name equality is a candidate only; neither GUID match nor runtime behavior verified.",
            "Do not substitute class name, object name, damage or ammunition for component identity.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = inspect(args.source_root, json.loads(args.index.read_text(encoding="utf-8")))
    result = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
