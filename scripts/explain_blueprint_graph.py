#!/usr/bin/env python3
"""Explain an explicit Blueprint package's reachable source graph.

This is a read-only topology inspection tool. Inheritance overrides, actual
firing-mode behavior, multi-ammo selection and native game rules require
separate evidence; reachability alone never proves a damage calculation.
"""
from __future__ import annotations

import argparse
from collections import deque
import json
from pathlib import Path

from scripts.diff_blueprint_graph import checked


def explain(graph, root_package: str, max_depth: int = 10, max_nodes: int = 250):
    graph = checked(graph)
    if not isinstance(root_package, str) or not root_package:
        raise ValueError("A non-empty exact Blueprint package name is required")
    if not isinstance(max_depth, int) or not 0 <= max_depth <= 32:
        raise ValueError("max_depth must be between 0 and 32")
    if not isinstance(max_nodes, int) or not 1 <= max_nodes <= 500:
        raise ValueError("max_nodes must be between 1 and 500")

    nodes = {node["package"]: node for node in graph["packages"]}
    if root_package not in nodes:
        raise ValueError("Root package is absent from this pinned export: " + root_package)
    outgoing = {}
    for edge in graph["object_references"]:
        outgoing.setdefault(edge["source"], []).append(edge)
    for group in outgoing.values():
        group.sort(key=lambda x: (str(x["record"]), x["field"], x["target"]))

    visited = {root_package}
    via = {root_package: []}
    q = deque([(root_package, 0)])
    links = []
    skipped_at_depth = 0
    while q:
        name, depth = q.popleft()
        for edge in outgoing.get(name, []):
            link = {
                "source": name,
                "source_sha256": edge["source_sha256"],
                "record": edge["record"], "field": edge["field"],
                "object_path": edge["object_path"], "target": edge["target"],
                "status": edge["status"],
            }
            links.append(link)
            if edge["status"] != "exported" or edge["target"] in visited:
                continue
            if depth == max_depth:
                skipped_at_depth += 1
                continue
            if len(visited) >= max_nodes:
                raise ValueError("Maximum reachable package count exceeded; no complete trace emitted")
            visited.add(edge["target"])
            via[edge["target"]] = via[name] + [{
                "from": name, "record": edge["record"],
                "field": edge["field"], "to": edge["target"],
            }]
            q.append((edge["target"], depth + 1))

    numeric = [x for x in graph["numeric_row_references"] if x["source"] in visited]
    declarations = [x for x in graph["declarations"] if x["source"] in visited]
    numeric.sort(key=lambda x: (x["source"], x["record"], x["field"], x["table"]))
    declarations.sort(key=lambda x: (x["source"], x["record"], x["field"]))
    missing_objects = [x for x in links if x["status"] == "missing_export"]
    missing_rows = [x for x in numeric if x["status"] != "row_present"]
    return {
        "schema_version": 1,
        "status": ("bounded_partial_explicit_graph" if skipped_at_depth else
                   "explicit_graph_with_unresolved_references" if missing_objects or missing_rows else
                   "explicit_graph_closure_for_recognized_edges"),
        "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "root_package": root_package,
        "safe_for_unattended_publication": False,
        "packages": [
            {"package": key, "sha256": nodes[key]["sha256"],
             "source_path": via[key], "depth": len(via[key])}
            for key in sorted(visited)
        ],
        "object_references": links,
        "numeric_row_references": numeric,
        "identifier_declarations": declarations,
        "gaps": {
            "missing_export_links": missing_objects,
            "unresolved_numeric_row_links": missing_rows,
            "edges_not_traversed_due_to_depth_limit": skipped_at_depth,
        },
        "limitations": [
            "Only recognized exported reference fields are followed.",
            "A linked class may be a parent or variant; topology does not assert a specific firing mode.",
            "Inherited property overrides are not flattened by this inspection command.",
            "Even a closed explicit graph does not establish gameplay damage or native code behavior.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--package", required=True, help="Exact package name relative to Blueprint root (no .json)")
    p.add_argument("--max-depth", type=int, default=10)
    p.add_argument("--max-nodes", type=int, default=250)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = explain(json.loads(args.index.read_text(encoding="utf-8")),
                     args.package, args.max_depth, args.max_nodes)
    data = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
