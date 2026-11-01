#!/usr/bin/env python3
"""Compare trusted FoxBunker per-tier data with exact *saved* structure rows.

Source-only research. The public third-party reference script is *read*,
validated by SHA256, parsed as a JSON-compatible literal, never executed.
Game rows are verified against a pinned Blueprint package graph. Only typed
original CodeName -> FName joins may be attributed to saved class defaults.

Numeric equality is a discovery filter, NOT a proof of class/tier identity or
of runtime-effective game behavior. No unattended writes to bot catalogs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

from scripts.audit_structure_dynamic_row_identity import TABLE_PACKAGE
from scripts.diff_blueprint_graph import checked
from scripts.resolve_blueprint_weapons import load
from scripts.triage_blueprint_inheritance_exceptions import exact_export

PUBLIC_REFERENCE_SHA256 = "9f781ca6f7f1d523c4a22f51dd380f0bc2ff38436d829098199de4209f9e69de"
REFERENCE_SOURCE = "https://foxbunker.com/bunker/js/utils.js"
MATCH_FIELDS = ("StructuralIntegrity", "MaxHealth", "RepairCost")
VALIDATED_BOT_ALIASES = {
    "Base": "core", "Blank": "piece", "Ramp": "ramp",
    "Med Bunker": "med", "Artillery Shelter": "shelter",
    "Rifle Garrison": "rg", "Machine Gun Garrison": "mg",
    "Observation Bunker": "obs", "Engine Room": "eng",
    "Anti-Tank Garrison": "atg", "Howitzer Garrison": "hg",
    "Ammo Room": "ammo", "Intelligence Center": "ic",
    "Storm Cannon": "sc", "Weather Station": "ws",
    "Underground Fortress": "fortress",
    "Interceptor Array": "radar",
}


def number(value):
    """Exact finite scalar comparison; no bool, string, unit or list coercion."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        value = Decimal(str(value))
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def reference_table(blob: bytes, digest: str = PUBLIC_REFERENCE_SHA256):
    if hashlib.sha256(blob).hexdigest() != digest:
        raise ValueError("FoxBunker source changed; revalidate before comparing")
    text = blob.decode("utf-8")
    match = re.search(r"\bconst\s+STRUCTURES\s*=\s*(\[.*?\])\s*;", text, re.S)
    if not match:
        raise ValueError("Missing exact public FoxBunker STRUCTURES literal")
    table = json.loads(match.group(1))
    if not isinstance(table, list) or len(table) != 22:
        raise ValueError("Reference structure count drift")
    parsed, names = [], set()
    for index, item in enumerate(table):
        if not isinstance(item, list) or len(item) != 4:
            raise ValueError("Malformed reference piece definition")
        name, shorthand, minimum_tier, values = item
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("Duplicate/malformed reference type")
        if (not isinstance(shorthand, str) or
                type(minimum_tier) is not int or minimum_tier not in (1, 2, 3) or
                not isinstance(values, list) or len(values) != 3):
            raise ValueError("Malformed reference tier declarations")
        names.add(name)
        tiers = []
        for tier, row in enumerate(values, start=1):
            if row is None:
                tiers.append(None)
                continue
            if not isinstance(row, list) or len(row) != 6:
                raise ValueError("Invalid reference per-tier tuple")
            nums = tuple(number(v) for v in row)
            if any(v is None for v in nums):
                raise ValueError("Non-numeric reference per-tier values")
            tiers.append(nums)
        if any(tiers[i] is None for i in range(minimum_tier - 1, 3)):
            raise ValueError("Missing tier at/above minimum tier")
        parsed.append({"id": index, "name": name, "abbr": shorthand,
                       "minimum_tier": minimum_tier, "tiers": tiers})
    if len(set(VALIDATED_BOT_ALIASES) - names):
        raise ValueError("Explicit alias missing reference type")
    return parsed


def collect_numeric_rows(rows):
    if not isinstance(rows, dict):
        raise ValueError("Malformed original game row map")
    accepted, rejected = {}, Counter()
    for name, row in sorted(rows.items()):
        if not isinstance(name, str) or not name or not isinstance(row, dict):
            raise ValueError("Invalid game table row")
        values = tuple(number(row.get(f)) for f in MATCH_FIELDS)
        if all(v is not None for v in values):
            accepted[name] = values
        else:
            rejected["missing_or_non_numeric_matched_fields"] += 1
    return accepted, rejected


def compare(reference, game_rows, typed_records):
    """typed_records must be the output of the verified source-only join audit."""
    if not isinstance(typed_records, list):
        raise ValueError("Missing exact source join records")
    attributed = defaultdict(list)
    for record in typed_records:
        if not isinstance(record, dict):
            raise ValueError("Invalid saved class identity report")
        identity = record.get("row_identity") or {}
        if identity.get("status") != "original_nameproperty_and_fname_row":
            continue
        row = identity.get("row")
        if not isinstance(row, str) or not row:
            raise ValueError("Typed identity missing row name")
        if row not in game_rows:
            # This does not imply a missing original row: only a missing
            # numeric triad eligible for this *reference comparison*.
            continue
        if identity.get("table") != TABLE_PACKAGE:
            raise ValueError("Unexpected typed identity table")
        if not record.get("package", "").startswith("Structures/"):
            raise ValueError("Typed structure class missing structure path")
        attributed[row].append({
            "package": record["package"],
            "saved_default_export": record["saved_default_export"],
            "source_sha256": record["source_sha256"],
        })
    comparisons = []
    for definition in reference:
        for tier, row in enumerate(definition["tiers"], start=1):
            base = {"reference_type": definition["name"],
                    "reference_abbr": definition["abbr"],
                    "reference_type_id": definition["id"],
                    "reference_tier": tier,
                    "existing_bot_alias": VALIDATED_BOT_ALIASES.get(definition["name"]),
                    "reference_status": "user_validated_foxbunker_gameplay_input",
                    "effective_runtime_mapping": "not_established",
                    "auto_publish": False}
            if row is None:
                comparisons.append({**base, "status": "reference_tier_unavailable",
                                    "numeric_match_rows": [], "typed_match_rows": []})
                continue
            # All three fields match precisely; never choose by display name
            # or the directory that a game object happens to reside in.
            expected = (row[0], row[1], row[2])
            matches = [name for name, values in game_rows.items() if values == expected]
            typed = [name for name in matches if attributed.get(name)]
            status = ("no_exact_numeric_row_candidate" if not matches else
                      "unattributed_numeric_row_candidates" if not typed else
                      "unique_typed_source_row_candidate" if len(typed) == 1 else
                      "ambiguous_typed_source_row_candidates")
            comparisons.append({
                **base, "status": status,
                "numeric_match_rows": matches,
                "typed_match_rows": [
                    {"row": name, "saved_declaring_classes": attributed[name]}
                    for name in typed
                ],
                "game_matched_values": "numeric_equal_to_reference_not_exposed",
            })
    return comparisons


def audit(root: Path, graph: dict, typed_report: dict, reference_bytes: bytes,
          reference_sha256: str = PUBLIC_REFERENCE_SHA256):
    graph = checked(graph)
    if (typed_report.get("source_build_id") != graph["source_build_id"] or
            typed_report.get("relation_digest") != graph["relation_digest"]):
        raise ValueError("Mismatched original typed join source build/graph")
    if typed_report.get("safe_for_unattended_publication") is not False:
        raise ValueError("Unrestricted source join report")
    if typed_report.get("coverage", {}).get("table_key_type") != "FName":
        raise ValueError("Original structure table row key was not proven FName")
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    if TABLE_PACKAGE not in nodes:
        raise ValueError("Missing indexed game source structure table")
    if typed_report["coverage"].get("structure_dynamic_table_sha256") != nodes[TABLE_PACKAGE]:
        raise ValueError("Typed report source table hash drift")
    exports = load(exact_export(root.resolve(), TABLE_PACKAGE, nodes[TABLE_PACKAGE]))
    if (not isinstance(exports, list) or len(exports) != 1 or
            not isinstance(exports[0], dict) or
            not isinstance(exports[0].get("Rows"), dict)):
        raise ValueError("Malformed pinned original structure table export")
    source_rows = exports[0]["Rows"]
    if len(source_rows) != typed_report["coverage"].get("table_rows"):
        raise ValueError("Source table row count drift")
    numeric_rows, rejected = collect_numeric_rows(source_rows)
    refs = reference_table(reference_bytes, reference_sha256)
    records = compare(refs, numeric_rows, typed_report["records"])
    summary = Counter(x["status"] for x in records)
    if not numeric_rows or not sum(bool(x["numeric_match_rows"]) for x in records):
        raise ValueError("No numeric game/reference overlap: investigate field semantics")
    return {
        "schema_version": 1,
        "status": "source_only_foxbunker_bunker_numeric_row_candidates",
        "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "game_structure_table_sha256": nodes[TABLE_PACKAGE],
        "source_join_inspector_commit": typed_report.get("inspector_commit"),
        "reference": {"url": REFERENCE_SOURCE, "sha256": reference_sha256,
                      "validation": "project_owner_explicitly_confirmed_gameplay_data_accuracy_2026_11_01"},
        "safe_for_unattended_publication": False,
        "coverage": {
            "reference_type_count": len(refs),
            "reference_available_tiers": sum(sum(t is not None for t in d["tiers"]) for d in refs),
            "game_structure_rows": len(source_rows),
            "game_rows_with_three_numeric_fields": len(numeric_rows),
            "game_rows_excluded_from_numeric_matching": dict(rejected),
            "comparison_status_counts": dict(sorted(summary.items())),
            "rows_with_any_numeric_candidate": sum(bool(x["numeric_match_rows"]) for x in records),
            "rows_with_any_original_typed_join_candidate": sum(bool(x["typed_match_rows"]) for x in records),
        },
        "records": records,
        "limitations": [
            "FoxBunker data is owner-validated, not proof of runtime inheritance or object identity.",
            "Matching three public values does not establish the same entity class, tier, or faction.",
            "Typed class join means original NameProperty to FName source row, not runtime-effective selection.",
            "Numeric coincidence is explicitly ambiguous; do not resolve by fuzzy class name.",
            "Only source rows with three uncoerced numeric scalar values are compared.",
            "No original game numeric values may be printed or written into public repositories.",
            "Do not update bot catalogs without separately reviewed and validated identity mappings.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--typed-report", type=Path, required=True)
    p.add_argument("--reference-js", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = audit(
        args.source_root,
        json.loads(args.index.read_text(encoding="utf-8")),
        json.loads(args.typed_report.read_text(encoding="utf-8")),
        args.reference_js.read_bytes())
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
