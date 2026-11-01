#!/usr/bin/env python3
"""Pair exact serialized InheritableComponentHandler record references.

An OwnerClass and ComponentTemplate on the SAME serialized record establish
source association, not reconstructed effective runtime component behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import re
from pathlib import Path

from scripts.diff_blueprint_graph import checked

FIELD = re.compile(r"^Records\[([0-9]+)\]\.(ComponentKey\.OwnerClass|ComponentTemplate)$")


def pair_records(graph):
    graph = checked(graph)
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate source package")
    records = {}
    for edge in graph["object_references"]:
        match = FIELD.fullmatch(edge["field"])
        if match is None:
            continue
        package, record, index = edge["source"], edge["record"], int(match.group(1))
        if package not in nodes or edge["source_sha256"] != nodes[package]:
            raise ValueError("Handler source hash differs from indexed package")
        key = (package, record, index)
        slot = "owner_class" if match.group(2) == "ComponentKey.OwnerClass" else "component_template"
        data = records.setdefault(key, {})
        if slot in data:
            raise ValueError("Duplicate handler field identity")
        data[slot] = {
            "object_path": edge["object_path"],
            "target_package": edge["target"],
            "target_export_status": edge["status"],
        }
    findings = []
    counts = Counter()
    for (package, record, index), data in sorted(records.items()):
        owner, template = data.get("owner_class"), data.get("component_template")
        status = ("both_blueprint_fields" if owner and template else
                  "owner_only_native_or_missing_template" if owner else
                  "template_only_native_or_missing_owner")
        counts[status] += 1
        if owner and owner["target_export_status"] != "exported":
            counts["owner_export_missing"] += 1
        if template and template["target_export_status"] != "exported":
            counts["template_export_missing"] += 1
        if owner and owner["target_package"] != package:
            counts["owner_cross_package"] += 1
        if template and template["target_package"] == package:
            counts["template_same_package"] += 1
        findings.append({
            "source_package": package,
            "source_sha256": nodes[package],
            "source_record": record,
            "record_index": index,
            "status": status,
            "owner_class": owner,
            "component_template": template,
            "effective_runtime_component": "not_established",
        })
    return {
        "schema_version": 1,
        "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "source_only_inheritable_component_record_pairs",
        "safe_for_unattended_publication": False,
        "coverage": {
            "record_pairs_with_blueprint_paths": len(findings),
            "source_status_counts": dict(sorted(counts.items())),
        },
        "records": findings,
        "limitations": [
            "Pairs describe serialized fields on the same handler record, not proven runtime overrides.",
            "Native/non-Blueprint fields are absent from indexed pairs, not necessarily absent from game assets.",
            "No selected ammo, seat, gameplay factor or CDO struct merging is inferred.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    result = pair_records(json.loads(a.index.read_text(encoding="utf-8")))
    out = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if a.output:
        a.output.write_text(out, encoding="utf-8")
    else:
        print(out, end="")


if __name__ == "__main__":
    main()
