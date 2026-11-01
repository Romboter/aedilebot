#!/usr/bin/env python3
"""Review-only audit of unindexed explicit Blueprint ObjectPath properties."""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.find_blueprint_dependencies import asset_path
from scripts.triage_blueprint_inheritance_exceptions import exact_export
from scripts.resolve_blueprint_weapons import load


def walk(value, path=(), depth=0):
    if depth > 32:
        raise ValueError("Excessive export property nesting")
    if isinstance(value, dict):
        if "ObjectPath" in value:
            yield ".".join(path), value["ObjectPath"]
        for k, v in sorted(value.items()):
            if k != "ObjectPath":
                yield from walk(v, path + (k,), depth + 1)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            if path:
                suffix = path[:-1] + (path[-1] + f"[{i}]",)
            else:
                suffix = (f"[{i}]",)
            yield from walk(v, suffix, depth + 1)


def scan(root, graph, max_refs=300000):
    graph = checked(graph)
    root = root.resolve()
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate source package")
    known = {(e["source"], e["record"], e["field"], e["object_path"])
             for e in graph["object_references"]}
    if len(known) != len(graph["object_references"]):
        raise ValueError("Duplicate indexed edge")
    confirmed = set()
    groups = defaultdict(lambda: {"counts": Counter(), "examples": [], "targets": set()})
    stats = Counter()
    for package in sorted(nodes):
        objects = load(exact_export(root, package, nodes[package]))
        if not isinstance(objects, list):
            raise ValueError("Invalid source export")
        for obj in objects:
            if not isinstance(obj, dict):
                raise ValueError("Invalid source object")
            name = obj.get("Name")
            kind = obj.get("Type", "unknown")
            for path, value in walk(obj):
                stats["all_objectpaths"] += 1
                if stats["all_objectpaths"] > max_refs:
                    raise ValueError("Too many object references")
                if not isinstance(value, str) or not value:
                    status, target = "invalid_reference", None
                else:
                    target = asset_path(value)
                    short = path.removeprefix("Properties.")
                    key = (package, name, short, value)
                    if target and key in known:
                        status = "indexed"
                        confirmed.add(key)
                    elif target:
                        status = "unindexed_blueprint"
                    else:
                        status = "external_or_native"
                stats[status] += 1
                family = (str(kind), re.sub(r"\[\d+\]", "[]", path))
                entry = groups[family]
                entry["counts"][status] += 1
                if target:
                    entry["targets"].add(target)
                if status == "unindexed_blueprint" and len(entry["examples"]) < 3:
                    entry["examples"].append({
                        "package": package, "sha256": nodes[package],
                        "record": name, "field": path, "target": target,
                    })
    if confirmed != known:
        raise ValueError("Graph indexed references absent from exact package exports")
    families = [{
        "type": t, "path": p, "counts": dict(sorted(v["counts"].items())),
        "distinct_targets": len(v["targets"]), "examples": v["examples"],
    } for (t, p), v in groups.items()]
    families.sort(key=lambda v: (-v["counts"].get("unindexed_blueprint", 0),
                                 v["type"], v["path"]))
    return {
        "schema_version": 1, "build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "read_only_objectpath_reference_surface",
        "safe_for_unattended_publication": False,
        "coverage": dict(sorted(stats.items())),
        "indexed_packages": len(nodes),
        "indexed_edges_verified": len(confirmed),
        "field_families": families,
        "limitations": [
            "Serialized ObjectPaths are candidates, not proven gameplay or ammo relations.",
            "Native defaults and bytecode references are not inspected.",
            "No inferred runtime CDO properties, damage or numeric aliases.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    report = scan(a.source_root, json.loads(a.index.read_text()))
    output = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if a.output:
        a.output.write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
