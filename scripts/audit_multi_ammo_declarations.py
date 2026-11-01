#!/usr/bin/env python3
"""Audit all explicitly serialized MultiAmmo Blueprint CDO declarations.

This is a read-only, build-scoped source inventory, not an effective runtime
CDO reconstruction or an ammunition/damage generator. Uses the complete,
pinned Blueprint graph index for discovery, not a hand-maintained target list.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.trace_multi_ammo_field_evidence import collect_nested_field_evidence
from scripts.triage_blueprint_inheritance_exceptions import (
    ammo_structure, class_default, lineage, parent_graph,
)


def _source_packages(index):
    """The graph emits one reference for every saved CDO MultiAmmo property."""
    return sorted({
        edge["source"] for edge in index["numeric_row_references"]
        if edge["field"] == "MultiAmmo"
        or edge["field"].startswith("MultiAmmo.CompatibleAmmoNames[")
    })


def audit(root: Path, index: dict):
    index = checked(index)
    root = root.resolve()
    nodes = {item["package"]: item["sha256"] for item in index["packages"]}
    parents, _ = parent_graph(index)
    report = []
    counts = Counter()
    for package in _source_packages(index):
        if package not in nodes:
            raise ValueError("Discovered MultiAmmo source missing from graph index: " + package)
        _, props = class_default(root, package, nodes)
        if "MultiAmmo" not in props:
            raise ValueError("Graph declared MultiAmmo but exact source no longer has it: " + package)
        saved = ammo_structure(props["MultiAmmo"])
        chain = lineage(package, parents, nodes)
        evidence = collect_nested_field_evidence(
            chain, nodes, lambda name: class_default(root, name, nodes))
        name_history = evidence["fields"]["CompatibleAmmoNames"]["source_declarations_nearest_first"]
        ancestors = [d for d in name_history if d["package"] != package
                     and d["shape"] == "explicit_names"]
        # The closest serialized ancestor is only a candidate, NOT effective.
        candidate = ancestors[0] if ancestors else None
        counts[saved["status"]] += 1
        if saved["status"] == "array_not_in_export":
            counts["partially_serialized_struct"] += 1
        if saved["status"] in {"array_not_in_export", "empty_array"} and candidate:
            counts["incomplete_or_empty_with_parent_candidate"] += 1
        if saved["status"] == "array_not_in_export" and candidate:
            counts["partial_with_parent_candidate"] += 1
        report.append({
            "component": package,
            "package_sha256": nodes[package],
            "saved_shape": saved["status"],
            "saved_field_names": saved.get("exported_field_names", []),
            "compatible_names_field_resolution": evidence["fields"]["CompatibleAmmoNames"]["resolution"],
            "filters_field_resolution": evidence["fields"]["AmmoSlotFilterAmounts"]["resolution"],
            "parent_name_candidate": ({
                "package": candidate["package"],
                "package_sha256": candidate["sha256"],
                "property_path": candidate["property_path"],
                "option_count": candidate["count"],
            } if candidate else None),
            "effective_at_runtime": "not_established",
        })
    return {
        "schema_version": 1,
        "source_build_id": index["source_build_id"],
        "relation_digest": index["relation_digest"],
        "status": "review_only_buildwide_multi_ammo_declaration_audit",
        "safe_for_unattended_publication": False,
        "coverage": {
            "blueprint_packages_in_index": len(nodes),
            "explicit_multi_ammo_cdo_packages": len(report),
            "counts": dict(sorted(counts.items())),
        },
        "declarations": report,
        "limitations": [
            "Saved JSON declarations are NOT reconstructed runtime CDO defaults.",
            "Parent name lists are source candidates only, never published effective ammunition.",
            "The graph index discovers only explicitly serialized CDO MultiAmmo; native and implicit modes are out of scope.",
            "No damage or multipliers are calculated; unknown inheritance and unverified gameplay rules remain unresolved.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    result = audit(a.source_root, json.loads(a.index.read_text(encoding="utf-8")))
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if a.output:
        a.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
