#!/usr/bin/env python3
"""Exact saved Structure.CodeName -> BPStructureDynamicData row identity audit.

A typed original FName tag plus FName DataTable key can prove an exact
serialized *source identifier* join, not engine runtime use of the row.
Never flatten CDO inheritance, select upgrade tiers or publish game values.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.find_blueprint_dependencies import asset_path
from scripts.index_blueprint_graph import canonical
from scripts.resolve_blueprint_weapons import load
from scripts.triage_blueprint_inheritance_exceptions import exact_export

TABLE_PACKAGE = "Data/BPStructureDynamicData"
ROOT_PREFIX = "War/Content/Blueprints/"
DYNAMIC_FIELDS = ("MaxHealth", "RepairCost", "StructuralIntegrity",
                  "DecayStartHours", "DecayDurationHours",
                  "ResourceAmounts", "AltResourceAmounts")
CLASS_FIELDS = ("Health", "MaxHealth", "ArmourType", "Tier", "DecaySupplyDrain")


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def value_shape(value):
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (float, int)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "struct"
    if value is None:
        return "null"
    return "unsupported"


def parse_type_log(content: str):
    """Parse original UE tag types and normalize only exact .uasset path suffixes."""
    def source_package(pak):
        if not pak.startswith(ROOT_PREFIX):
            raise ValueError("Unscoped original inspector package type tag")
        # CUE4Parse's raw provider key includes '.uasset' while the
        # exported JSON/index uses package names without extensions.
        key = pak[len(ROOT_PREFIX):]
        if key.endswith(".uasset"):
            key = key[:-7]
        if not key or "." in key or "\\" in key:
            raise ValueError("Unsupported inspector package path")
        return key

    types, tables = {}, {}
    for raw in content.splitlines():
        fields = raw.split("\t")
        if len(fields) == 5 and fields[0] == "TYPE" and fields[3] == "CodeName":
            _, pak, obj, field, original_type = fields
            key = (source_package(pak), obj)
            if key in types:
                raise ValueError("Duplicate original CodeName tag")
            types[key] = original_type
        elif len(fields) == 4 and fields[0] == "TABLE":
            _, pak, name, key_type = fields
            if source_package(pak) == TABLE_PACKAGE:
                if name in tables:
                    raise ValueError("Duplicate table type tag")
                tables[name] = key_type
    return types, tables


def audit(root: Path, graph: dict, inspector_log: str | None = None,
          inspector_commit: str | None = None):
    graph = checked(graph)
    root = root.resolve()
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate indexed package")
    if TABLE_PACKAGE not in nodes:
        raise ValueError("Missing exact indexed structure DataTable")
    raw_table = load(exact_export(root, TABLE_PACKAGE, nodes[TABLE_PACKAGE]))
    tables = [o for o in raw_table if isinstance(o, dict) and isinstance(o.get("Rows"), dict)]
    if len(tables) != 1 or len(raw_table) != 1:
        raise ValueError("Missing or ambiguous structure DataTable export")
    table = tables[0]
    table_name = table.get("Name")
    if not isinstance(table_name, str):
        raise ValueError("Missing DataTable export name")
    rows = table["Rows"]
    if not all(isinstance(k, str) and isinstance(v, dict) for k, v in rows.items()):
        raise ValueError("Invalid structure row shape")
    if inspector_log is not None and not inspector_commit:
        raise ValueError("Original-tag inspector requires a pinned commit")
    types, table_types = parse_type_log(inspector_log or "")
    table_key_type = table_types.get(table_name)
    if table_types and len(table_types) != 1:
        raise ValueError("Unexpected multiple structure DataTable type tags")
    # Presence of CUE4Parse's generic DataTable row FName type is independent
    # of the serialized class-default CodeName property's original UE tag.
    if table_key_type is not None and table_key_type != "FName":
        raise ValueError("Unexpected structure table row key type")

    declaration_map = {}
    for d in graph["declarations"]:
        if d["field"] != "CodeName" or not d["source"].startswith("Structures/"):
            continue
        key = (d["source"], d["record"])
        if key in declaration_map:
            raise ValueError("Duplicate CodeName declaration")
        if d["source_sha256"] != nodes[d["source"]]:
            raise ValueError("Drifted source declaration hash")
        declaration_map[key] = d
    found_declarations, entries, counts = set(), [], Counter()
    target_by_row = Counter()

    for package in sorted(p for p in nodes if p.startswith("Structures/")):
        objects = load(exact_export(root, package, nodes[package]))
        if not isinstance(objects, list) or any(not isinstance(o, dict) for o in objects):
            raise ValueError("Malformed source structure package")
        names = Counter(o.get("Name") for o in objects
                        if isinstance(o.get("Name"), str))
        generated = [o for o in objects if o.get("Type") == "BlueprintGeneratedClass"]
        for klass in generated:
            cls = klass.get("Name")
            if not isinstance(cls, str):
                raise ValueError("Invalid generated structure class name")
            default = "Default__" + cls
            if names[default] != 1:
                counts["not_unique_saved_class_default"] += 1
                continue
            obj = next(o for o in objects if o.get("Name") == default)
            props = obj.get("Properties") or {}
            if not isinstance(props, dict):
                raise ValueError("Malformed saved structure default properties")
            declared = declaration_map.get((package, default))
            if declared is None:
                if "CodeName" in props:
                    raise ValueError("Saved CodeName not indexed in graph")
                counts["codename_not_serialized"] += 1
                continue
            found_declarations.add((package, default))
            if props.get("CodeName") != declared["value"]:
                raise ValueError("Graph declaration not found in exact source")
            name = declared["value"]
            original_tag = types.get((package, default))
            saved_type = "NameProperty" if original_tag == "NameProperty" else (
                "not_inspected" if original_tag is None else "other_original_tag")
            row = rows.get(name) if isinstance(name, str) else None
            case_matches = (
                sorted(k for k in rows if k != name and k.casefold() == name.casefold())
                if isinstance(name, str) and row is None else [])
            status = (
                "malformed_codename" if not isinstance(name, str) or not name else
                "unset_none_name_candidate" if name == "None" else
                "missing_exact_row" if row is None else
                "original_nameproperty_and_fname_row" if
                saved_type == "NameProperty" and table_key_type == "FName" else
                "saved_string_row_match_type_unverified")
            counts[status] += 1
            if row is not None:
                target_by_row[name] += 1
            parent_obj = klass.get("SuperStruct")
            parent_path = parent_obj.get("ObjectPath") if isinstance(parent_obj, dict) else None
            parent_pkg = asset_path(parent_path) if isinstance(parent_path, str) else None
            class_saved = {}
            for field in CLASS_FIELDS:
                class_saved[field] = ({
                    "status": "explicit_saved", "shape": value_shape(props[field]),
                    "value_sha256": fingerprint(props[field]),
                } if field in props else {"status": "not_serialized"})
            dynamic_saved = {}
            if row is not None:
                for field in DYNAMIC_FIELDS:
                    dynamic_saved[field] = ({
                        "status": "exact_row_field_present", "shape": value_shape(row[field]),
                        "value_sha256": fingerprint(row[field]),
                    } if field in row else {"status": "row_field_missing"})
            entries.append({
                "package": package, "source_sha256": nodes[package],
                "generated_class": cls, "saved_default_export": default,
                "field": "CodeName", "saved_codename": name,
                "saved_original_field_type": saved_type,
                "row_identity": {"table": TABLE_PACKAGE,
                                 "table_sha256": nodes[TABLE_PACKAGE],
                                 "row": name if row is not None else None,
                                 "status": status,
                                 "case_only_candidates_unverified": case_matches},
                "parent_source_candidate": parent_pkg,
                "parent_exported": parent_pkg in nodes if parent_pkg else False,
                "saved_class_fields": class_saved,
                "saved_row_fields": dynamic_saved,
                "effective_runtime_structure": "not_established",
                "effective_runtime_row_values": "not_established",
                "safe_for_unattended_publication": False,
            })
    if found_declarations != set(declaration_map):
        raise ValueError("Indexed CodeName declarations not represented by exact generated class default")
    if inspector_log is not None and table_key_type != "FName":
        raise ValueError("Original DataTable FName row key proof missing")
    return {
        "schema_version": 1, "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "review_only_structure_dynamic_codename_source_identity",
        "safe_for_unattended_publication": False,
        "coverage": {
            "structure_dynamic_table_sha256": nodes[TABLE_PACKAGE],
            "table_rows": len(rows),
            "table_key_type": table_key_type or "not_inspected",
            "saved_codename_records": len(entries),
            "status_counts": dict(sorted(counts.items())),
            "distinct_matched_rows": len(target_by_row),
            "multiply_referenced_rows": sum(v > 1 for v in target_by_row.values()),
        },
        "inspector_commit": inspector_commit,
        "inspector_log_sha256": (hashlib.sha256(inspector_log.encode()).hexdigest()
                                 if inspector_log is not None else None),
        "records": entries,
        "limitations": [
            "Typed source identifier and exact table row presence do not prove the game consumes that row at runtime.",
            "Saved class defaults do not imply effective inherited health, armour or tier.",
            "Missing CodeName in child is not inherited here; no name guessing or case-only joins.",
            "Structure dynamic field value hashes record source presence, not effective combat semantics.",
            "No production data, damage matrix or bunker structural topology is inferred.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", required=True, type=Path)
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--inspector-log", type=Path)
    p.add_argument("--inspector-commit")
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    inspector_log = (a.inspector_log.read_text(encoding="utf-8")
                     if a.inspector_log else None)
    result = audit(a.source_root,
                   json.loads(a.index.read_text(encoding="utf-8")),
                   inspector_log, a.inspector_commit)
    output = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if a.output:
        a.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
