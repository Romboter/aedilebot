#!/usr/bin/env python3
"""Review-only UE FName named-row resolution backed by per-field PAK type evidence.

Exact identifiers are always preserved. A case-only row is eligible as a
*verified identity candidate* only when this same pinned PAK was independently
inspected for an original NameProperty and UDataTable's FName row key. This
does not authorize game damage or production data updates. Native/unknown
properties, missing rows, ambiguous casefold matches, malformed fields, and
missing evidence fail closed. No guessed identifiers and no silent aliases.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.index_blueprint_graph import check_name, table_data


PREFIX = "War/Content/Blueprints/"
TABLES = {
    "BPAmmoDynamicData": "Data/BPAmmoDynamicData",
    "BPMountDynamicData": "Data/BPMountDynamicData",
}


def parse_inspection(text: str):
    """Parse the restricted inspector's TYPE/TABLE lines; never accept values."""
    types, tables = {}, {}
    unresolved = []
    for line in text.splitlines():
        if not line.startswith(("TYPE\t", "TABLE\t", "UNRESOLVED\t")):
            continue
        parts = line.split("\t")
        if parts[0] == "TABLE":
            if len(parts) != 4:
                raise ValueError("Malformed TABLE inspector record")
            _, path, record, row_key_type = parts
            if not path.startswith(PREFIX) or not path.endswith(".uasset") or not record:
                raise ValueError("Unsafe TABLE record")
            package = path[len(PREFIX):-7]
            if not all(check_name(part) for part in package.split("/")):
                raise ValueError("Unsafe TABLE package")
            identity = package
            if identity in tables:
                raise ValueError("Duplicate TABLE type record")
            tables[identity] = {"record": record, "key_type": row_key_type}
        else:
            if len(parts) != 5:
                raise ValueError("Malformed property inspector record")
            kind, path, record, field, type_name = parts
            if not path.startswith(PREFIX) or not path.endswith(".uasset") or not record or not field:
                raise ValueError("Unsafe property inspector record")
            package = path[len(PREFIX):-7]
            if not all(check_name(part) for part in package.split("/")):
                raise ValueError("Unsafe property package")
            identity = (package, record, field)
            if kind == "UNRESOLVED":
                unresolved.append({"package": package, "record": record, "field": field,
                                   "reason": type_name})
                continue
            if identity in types:
                raise ValueError("Duplicate TYPE record")
            types[identity] = type_name
    return types, tables, unresolved


def resolve(index: dict, export_root: Path, inspector_output: str, game_build_id: str,
            pak_sha256: str):
    checked(index)
    if index["source_build_id"] != game_build_id:
        raise ValueError("Index and local game build differ")
    if len(pak_sha256) != 64 or any(c not in "0123456789abcdef" for c in pak_sha256):
        raise ValueError("Pinned lowercase PAK SHA-256 required")
    root = export_root.resolve()
    actual_tables = table_data(root)
    for table in TABLES:
        if actual_tables[table]["sha256"] != index["table_exports"][table]["sha256"]:
            raise ValueError("Dynamic DataTable checksum mismatches indexed export: " + table)
    type_evidence, table_evidence, unresolved = parse_inspection(inspector_output)
    # The private runner must generate TYPE/TABLE lines from the same mounted
    # source PAK and pin the Steam build/PAK checksum in its own report.
    verified_tables = {
        table: table_evidence.get(package, {}).get("key_type") == "FName"
        for table, package in TABLES.items()
    }
    packages = {obj["package"]: obj["sha256"] for obj in index["packages"]}
    observations = []
    for ref in index["numeric_row_references"]:
        if ref["status"] not in {"row_missing", "invalid_identifier"}:
            continue
        source = ref["source"]
        if packages.get(source) != ref["source_sha256"]:
            raise ValueError("Source SHA provenance mismatch in graph: " + source)
        original = ref["row"]
        table = ref["table"]
        report = {
            "source": source, "source_sha256": ref["source_sha256"],
            "record": ref["record"], "field": ref["field"],
            "table": table, "declared_row": original,
            "original_status": ref["status"],
            "status": "unresolved", "matched_row": None,
            "source_type": type_evidence.get((source, ref["record"], ref["field"])),
            "table_key_type": table_evidence.get(TABLES[table], {}).get("key_type"),
            "candidate_rows": [],
            "safe_for_unattended_publication": False,
        }
        if ref["status"] == "invalid_identifier":
            report["reason"] = "invalid_declared_identifier"
        elif report["source_type"] != "NameProperty":
            report["reason"] = "original_nameproperty_type_unverified"
        elif not verified_tables[table]:
            report["reason"] = "datatable_fname_key_unverified"
        else:
            rows = actual_tables[table]["rows"]
            if rows is None:
                report["reason"] = "datatable_unavailable"
            else:
                # ASCII names only: our lexical normalization cannot extend
                # FName's runtime semantics to arbitrary Unicode strings.
                candidates = sorted(
                    key for key in rows
                    if isinstance(key, str) and check_name(key) and key.lower() == original.lower()
                )
                report["candidate_rows"] = candidates
                if len(candidates) == 1:
                    report["status"] = "typed_fname_unique_row_identity"
                    report["matched_row"] = candidates[0]
                    report["reason"] = "unique_fname_case_insensitive_join"
                elif len(candidates) > 1:
                    report["reason"] = "ambiguous_fname_row_keys"
                else:
                    report["reason"] = "no_matching_named_row"
        observations.append(report)
    counts = Counter(entry["status"] for entry in observations)
    reasons = Counter(entry["reason"] for entry in observations)
    return {
        "schema_version": 1,
        "game_build_id": game_build_id,
        "pak_sha256": pak_sha256,
        "relation_digest": index["relation_digest"],
        "status": "review_only_typed_fname_evidence",
        "safe_for_unattended_publication": False,
        "verified_table_key_types": verified_tables,
        "inspected_property_type_records": len(type_evidence),
        "inspector_unresolved_fields": unresolved,
        "counts": {"eligible_and_unique": counts.get("typed_fname_unique_row_identity", 0),
                   "unresolved": counts.get("unresolved", 0),
                   "reasons": dict(sorted(reasons.items()))},
        "observations": observations,
        "limitations": [
            "Only exact fields inspected from the same private PAK qualify for typed FName lookup.",
            "The caller must pin inspector output, Steam build, and SHA-256 to the same PAK; this is not a signed attestation.",
            "A unique row name identity does not prove ammo/mount gameplay numeric correctness.",
            "No inferred aliases, native code assumptions, unattended publication, or production writes.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--inspector-output", type=Path, required=True)
    p.add_argument("--build-id", required=True)
    p.add_argument("--pak-sha256", required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = resolve(json.loads(args.index.read_text(encoding="utf-8")),
                     args.source_root, args.inspector_output.read_text(encoding="utf-8"),
                     args.build_id, args.pak_sha256)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
