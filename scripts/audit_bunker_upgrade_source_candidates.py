#!/usr/bin/env python3
"""Source-only upgrade edge evidence for ambiguous FoxBunker bunker tier candidates.

Compare explicit saved UpgradeStructureCodeName declarations to source-verified
CodeName/FName rows. Do not infer that a saved upgrade is an executable action,
that its target is the effective runtime successor, or that matching a
FoxBunker numeric profile resolves a class identity.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.index_blueprint_graph import canonical
from scripts.resolve_blueprint_weapons import load
from scripts.triage_blueprint_inheritance_exceptions import exact_export
from scripts.audit_structure_dynamic_row_identity import TABLE_PACKAGE


def shape(value):
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, dict):
        return "struct"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    return "unsupported"


def prepare(typed_records, benchmark_records):
    """Separate original type-confirmed class declarations from numeric matches."""
    typed_by_row = defaultdict(list)
    for record in typed_records:
        identity = record.get("row_identity", {})
        if identity.get("status") != "original_nameproperty_and_fname_row":
            continue
        row = identity.get("row")
        if not isinstance(row, str) or not row:
            raise ValueError("Malformed type-confirmed source row")
        typed_by_row[row].append(record)

    reference_profiles = defaultdict(list)
    for record in benchmark_records:
        if record.get("status") == "reference_tier_unavailable":
            continue
        tier = record.get("reference_tier")
        if type(tier) is not int or tier not in (1, 2, 3):
            raise ValueError("Malformed FoxBunker candidate tier")
        piece = record.get("reference_type")
        if not isinstance(piece, str) or not piece:
            raise ValueError("Malformed FoxBunker candidate label")
        for row in record.get("typed_match_rows", []):
            name = row.get("row")
            if name not in typed_by_row:
                raise ValueError("Benchmark invented an unverified source identity")
            key = (piece, tier)
            if key in reference_profiles[name]:
                raise ValueError("Duplicate FoxBunker profile-row attribution")
            reference_profiles[name].append(key)
    return typed_by_row, reference_profiles


def parse_original_upgrade_types(content: str):
    """Only original UE property TYPE tags; values are never accepted."""
    result = {}
    prefix = "War/Content/Blueprints/"
    for line in content.splitlines():
        cols = line.split("\t")
        if len(cols) != 5 or cols[0] != "TYPE" or cols[3] != "UpgradeStructureCodeName":
            continue
        _, path, name, _, kind = cols
        if not path.startswith(prefix):
            raise ValueError("Unscoped original upgrade tag")
        pkg = path[len(prefix):]
        if pkg.endswith(".uasset"):
            pkg = pkg[:-7]
        if not pkg.startswith("Structures/") or "." in pkg or "\\" in pkg:
            raise ValueError("Invalid original upgrade package path")
        if not name.startswith("Default__") or not kind:
            raise ValueError("Malformed original upgrade tag")
        key = (pkg, name)
        if key in result:
            raise ValueError("Duplicate original upgrade tag")
        result[key] = kind
    return result


def inspect_declared_upgrade(default_properties, rows, source_profiles, target_profiles,
                             original_tag=None):
    """No name inference. Only same-reference next-tier source candidates counted."""
    if not isinstance(default_properties, dict):
        raise ValueError("Malformed saved class default properties")
    if "UpgradeStructureCodeName" not in default_properties:
        return {"status": "upgrade_not_serialized"}
    value = default_properties["UpgradeStructureCodeName"]
    if not isinstance(value, str) or not value:
        return {"status": "upgrade_saved_non_name_scalar",
                "shape": shape(value)}
    if value == "None":
        return {"status": "upgrade_saved_none_name_sentinel"}
    if value not in rows:
        return {"status": "upgrade_saved_target_not_in_original_structure_table",
                "saved_target_codename": value}
    reference_steps = sorted(
        ({"type": piece, "from_tier": tier, "to_tier": tier + 1}
         for piece, tier in source_profiles
         if (piece, tier + 1) in target_profiles),
        key=lambda step: (step["type"], step["from_tier"], step["to_tier"]))
    return {
        "status": ("exact_saved_target_with_reference_tier_step_candidates"
                   if reference_steps else
                   "exact_saved_target_without_reference_tier_step"),
        "saved_target_codename": value,
        "same_reference_next_tier_candidates": reference_steps,
        "original_upgrade_property_type": original_tag or "not_inspected",
        "runtime_upgrade_behavior": "not_established",
    }


def audit(root: Path, graph: dict, typed_report: dict, benchmark_report: dict,\n          original_type_log: str | None = None, inspector_commit: str | None = None):
    graph = checked(graph)
    for name, report in (("typed", typed_report), ("benchmark", benchmark_report)):
        if not isinstance(report, dict):
            raise ValueError("Malformed " + name + " report")
        if (report.get("source_build_id") != graph["source_build_id"]
                or report.get("relation_digest") != graph["relation_digest"]
                or report.get("safe_for_unattended_publication") is not False):
            raise ValueError("Unverified or mismatched " + name + " report")
    if typed_report.get("coverage", {}).get("table_key_type") != "FName":
        raise ValueError("Missing original FName row key proof")
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    if typed_report.get("coverage", {}).get("structure_dynamic_table_sha256") != nodes.get(TABLE_PACKAGE):
        raise ValueError("Original typed report structure table SHA drift")
    if benchmark_report.get("game_structure_table_sha256") != nodes.get(TABLE_PACKAGE):
        raise ValueError("Benchmark game table SHA drift")
    if benchmark_report.get("reference", {}).get("validation") != (
            "project_owner_explicitly_confirmed_gameplay_data_accuracy_2026_11_01"):
        raise ValueError("Unexpected public benchmark validation provenance")

    if original_type_log is not None and not inspector_commit:
        raise ValueError("Original upgrade type inspection requires pinned extractor commit")
    upgrade_tags = parse_original_upgrade_types(original_type_log or "")
    if original_type_log is not None and not upgrade_tags:
        raise ValueError("No original upgrade type tags inspected")
    root = root.resolve()
    table_export = load(exact_export(root, TABLE_PACKAGE, nodes[TABLE_PACKAGE]))
    if (not isinstance(table_export, list) or len(table_export) != 1
            or not isinstance(table_export[0].get("Rows"), dict)):
        raise ValueError("Malformed structure DataTable export")
    game_rows = table_export[0]["Rows"]
    typed_rows, reference_rows = prepare(typed_report["records"], benchmark_report["records"])
    if not typed_rows or not reference_rows:
        raise ValueError("Missing validated benchmark candidates")
    source_cache = {}
    observations = []
    count = Counter()
    for row, refs in sorted(typed_rows.items()):
        for rec in refs:
            pkg = rec["package"]
            if pkg not in nodes or rec["source_sha256"] != nodes[pkg]:
                raise ValueError("Typed source package SHA drift")
            if pkg not in source_cache:
                source_cache[pkg] = load(exact_export(root, pkg, nodes[pkg]))
            exports = source_cache[pkg]
            name = rec["saved_default_export"]
            defaults = [o for o in exports if isinstance(o, dict) and o.get("Name") == name]
            if len(defaults) != 1:
                raise ValueError("Nonunique saved source default")
            props = defaults[0].get("Properties") or {}
            if not isinstance(props, dict) or props.get("CodeName") != row:
                raise ValueError("Original typed CodeName no longer matches source")
            target = props.get("UpgradeStructureCodeName")
            tag = upgrade_tags.get((pkg, name))
            if original_type_log is not None and "UpgradeStructureCodeName" in props and tag is None:
                raise ValueError("Saved upgrade lacks original UE field type tag")
            if original_type_log is not None and "UpgradeStructureCodeName" not in props and tag is not None:
                raise ValueError("Original upgrade tag without saved field")
            profile = inspect_declared_upgrade(
                props, game_rows, reference_rows.get(row, []),
                reference_rows.get(target, []) if isinstance(target, str) else [],
                original_tag=tag)
            count[profile["status"]] += 1
            tier_saved = props.get("Tier")
            observations.append({
                "package": pkg, "package_sha256": nodes[pkg],
                "saved_default_export": name, "saved_codename": row,
                "source_reference_profiles": [
                    {"reference_type": piece, "reference_tier": tier}
                    for piece, tier in sorted(reference_rows.get(row, []))
                ],
                "saved_tier": {"status": "explicit_saved",
                               "shape": shape(tier_saved),
                               "value_sha256": hashlib.sha256(canonical(tier_saved).encode()).hexdigest()}
                              if "Tier" in props else {"status": "not_serialized"},
                "saved_upgrade": profile,
                "effective_runtime_target": "not_established",
                "auto_publish": False,
            })
    linked = [o for o in observations if o["saved_upgrade"].get("same_reference_next_tier_candidates")]
    return {
        "schema_version": 1,
        "status": "saved_upgrade_declared_source_candidates_only",
        "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "table_sha256": nodes[TABLE_PACKAGE],
        "reference_sha256": benchmark_report["reference"]["sha256"],
        "safe_for_unattended_publication": False,
        "original_upgrade_inspector_commit": inspector_commit,
        "original_upgrade_type_log_sha256": (
            hashlib.sha256(original_type_log.encode()).hexdigest()
            if original_type_log is not None else None),
        "coverage": {
            "verified_typed_rows_in_source": len(typed_rows),
            "typed_class_declarations_checked": len(observations),
            "reference_row_identifiers": len(reference_rows),
            "saved_upgrade_status_counts": dict(sorted(count.items())),
            "same_reference_next_tier_candidate_links": len(linked),
            "saved_tier_property_present": sum(o["saved_tier"]["status"] == "explicit_saved" for o in observations),
            "original_upgrade_tag_count": len(upgrade_tags),
            "original_upgrade_tag_type_counts": dict(sorted(Counter(upgrade_tags.values()).items())),
        },
        "observations": observations,
        "limitations": [
            "UpgradeStructureCodeName UE tag proof requires a separately pinned original inspector; runtime behavior remains unproven.",
            "Exact upgrade row key alone does not prove an executable runtime upgrade or class selection.",
            "A reference-compatible tier step is a candidate, not an automatic class identity.",
            "Matching three numeric fields can group unrelated structures and different gameplay roles.",
            "Do not assume absent Tier or UpgradeStructureCodeName is inherited or unset in runtime.",
            "No production data, game numeric values, or bot catalogs may be published or modified.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--typed-report", type=Path, required=True)
    p.add_argument("--benchmark-report", type=Path, required=True)
    p.add_argument("--inspector-log", type=Path)\n    p.add_argument("--inspector-commit")\n    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = audit(
        a.source_root,
        json.loads(a.index.read_text(encoding="utf-8")),
        json.loads(a.typed_report.read_text(encoding="utf-8")),
        json.loads(a.benchmark_report.read_text(encoding="utf-8")),\n        a.inspector_log.read_text(encoding="utf-8") if a.inspector_log else None,\n        a.inspector_commit)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
