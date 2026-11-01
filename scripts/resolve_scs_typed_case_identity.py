#!/usr/bin/env python3
"""Type-gated, case-only FName SOURCE identity for SCS keys; not runtime CDO."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import re
from pathlib import Path

from scripts.diff_blueprint_graph import checked

PREFIX = "War/Content/Blueprints/"
TAG_KINDS = {"SCSKEYTYPE", "SCSNODETYPE"}


def parse_original_tags(text: str, graph: dict, inspector_commit: str):
    graph = checked(graph)
    if not re.fullmatch(r"[0-9a-f]{40}", inspector_commit):
        raise ValueError("Pinned inspector commit SHA required")
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    tags = {}
    for line in text.splitlines():
        fields = line.split(chr(9))
        if not fields or fields[0] not in TAG_KINDS:
            continue
        if len(fields) != 5:
            raise ValueError("Malformed original-tag evidence")
        kind, raw_package, record, field, tag_type = fields
        if not raw_package.startswith(PREFIX) or not raw_package.endswith(".uasset"):
            raise ValueError("Unsafe tag source package")
        package = raw_package[len(PREFIX):-7]
        if package not in nodes:
            raise ValueError("Original tag package is not in graph index")
        key = (kind, package, record, field)
        if key in tags:
            raise ValueError("Duplicated original property tag evidence")
        tags[key] = {"type": tag_type, "source_sha256": nodes[package]}
    if not tags:
        raise ValueError("No original tagged SCS types")
    return {
        "schema_version": 1,
        "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "inspector_commit": inspector_commit,
        "status": "original_ue_tag_evidence_only",
        "safe_for_unattended_publication": False,
        "tags": [
            {"kind": a, "package": b, "record": c, "field": d, **value}
            for (a,b,c,d), value in sorted(tags.items())
        ],
    }


def review(graph: dict, matched: dict, evidence: dict):
    graph = checked(graph)
    if (matched.get("source_build_id") != graph["source_build_id"]
            or matched.get("relation_digest") != graph["relation_digest"]
            or matched.get("safe_for_unattended_publication") is not False
            or matched.get("status") != "review_only_serialized_scs_key_matches"):
        raise ValueError("Mismatch in upstream source-only matcher provenance")
    if (evidence.get("schema_version") != 1
            or evidence.get("source_build_id") != graph["source_build_id"]
            or evidence.get("relation_digest") != graph["relation_digest"]
            or evidence.get("safe_for_unattended_publication") is not False
            or not re.fullmatch(r"[0-9a-f]{40}", evidence.get("inspector_commit", ""))):
        raise ValueError("Unpinned or invalid original property-tag evidence")
    packages = {x["package"]: x["sha256"] for x in graph["packages"]}
    if len(packages) != len(graph["packages"]):
        raise ValueError("Duplicated indexed packages")
    tags = {}
    for entry in evidence.get("tags", []):
        if entry["package"] not in packages or entry["source_sha256"] != packages[entry["package"]]:
            raise ValueError("Original-tag source package hash mismatch")
        key = (entry["kind"], entry["package"], entry["record"], entry["field"])
        if key in tags:
            raise ValueError("Duplicated original tag entry")
        tags[key] = entry["type"]

    def expect(kind, package, record, field, required_type):
        return tags.get((kind, package, record, field)) == required_type

    findings, counts = [], Counter()
    for rec in matched["records"]:
        if rec["status"] != "name_guid_disagreement":
            continue
        candidate = rec.get("guid_only_diagnostic")
        owner = rec.get("owner_class")
        child = rec["child"]
        index = rec["record_index"]
        if rec["source_sha256"] != packages.get(child):
            raise ValueError("Stale child source hash")
        if candidate is not None and candidate["parent_sha256"] != packages.get(candidate["parent_package"]):
            raise ValueError("Stale parent source hash")
        status = "source_case_identity_unverified"
        if (candidate and owner and owner["target_package"] == candidate["parent_package"]
                and candidate["accepted_as_exact_match"] is False
                and rec["parent_scs_match"] is None
                and rec["candidate_counts"] == {"name": 0, "guid": 1, "exact": 0}):
            child_name, parent_name = candidate["child_saved_key_name"], candidate["parent_saved_variable_name"]
            parent, node = candidate["parent_package"], candidate["parent_scs_node_record"]
            if (isinstance(child_name,str) and isinstance(parent_name,str)
                    and child_name.isascii() and parent_name.isascii()
                    and child_name != parent_name and child_name.lower() == parent_name.lower()):
                checks = (
                    ("SCSKEYTYPE", child, rec["handler_record"], f"Records[{index}].ComponentKey.OwnerClass", "ObjectProperty"),
                    ("SCSKEYTYPE", child, rec["handler_record"], f"Records[{index}].ComponentKey.SCSVariableName", "NameProperty"),
                    ("SCSKEYTYPE", child, rec["handler_record"], f"Records[{index}].ComponentKey.AssociatedGuid", "StructProperty"),
                    ("SCSNODETYPE", parent, node, "InternalVariableName", "NameProperty"),
                    ("SCSNODETYPE", parent, node, "VariableGuid", "StructProperty"),
                )
                if all(expect(*check) for check in checks):
                    status = "verified_typed_fname_case_only_source_identity"
        counts[status] += 1
        findings.append({
            "child": child, "record_index": index,
            "parent_package": candidate["parent_package"] if candidate else None,
            "parent_scs_node": candidate["parent_scs_node_record"] if candidate else None,
            "status": status,
            "original_tag_evidence_commit": evidence["inspector_commit"],
            "effective_runtime_component": "not_established",
        })
    return {
        "schema_version": 1, "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "review_only_type_gated_scs_case_identity",
        "safe_for_unattended_publication": False,
        "counts": dict(sorted(counts.items())),
        "reviewed_candidates": findings,
        "limitations": [
            "A type-verified case-only FName source identity does not establish runtime CDO or component override behavior.",
            "Every missing, conflicting or ambiguous tag and source is denied rather than repaired.",
            "No numeric values, selected ammunition or production publication.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--matching-report", type=Path, required=True)
    p.add_argument("--inspector-tags", type=Path, required=True)
    p.add_argument("--inspector-commit", required=True)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    graph = json.loads(a.index.read_text(encoding="utf-8"))
    typed = parse_original_tags(a.inspector_tags.read_text(encoding="utf-8"), graph, a.inspector_commit)
    result = review(graph, json.loads(a.matching_report.read_text(encoding="utf-8")), typed)
    serialized = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if a.output:
        a.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
