#!/usr/bin/env python3
"""Source-only survey of the precise calculator-relevant asset field surface.

Collects serialized field *shapes*, provenance and source checksums, not
runtime damage rules, effective CDOs, or human catalog mappings. Full reports
are private, with only bounded aggregates printed by the runner.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.find_blueprint_dependencies import asset_path
from scripts.index_blueprint_graph import canonical
from scripts.resolve_blueprint_weapons import load
from scripts.triage_blueprint_inheritance_exceptions import exact_export

ROOTS = ("DamageTypes", "Structures", "Vehicles", "Items", "Data")
HINTS = (
    "health", "damage", "armour", "armor", "resist", "mitigat",
    "penetrat", "repair", "decay", "integrity", "structure",
    "disable", "bunker", "build", "upgrade", "tier", "ammo",
    "projectile", "mount", "weapon", "range", "fire", "reload",
    "cost", "explosion",
)


def shape(value):
    if isinstance(value, dict):
        if isinstance(value.get("ObjectPath"), str):
            return "object_reference"
        return "struct"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "unsupported"


def field_relevant(name, root):
    return root == "DamageTypes" or any(token in name.lower() for token in HINTS)


def source_hash(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def inspect(root: Path, graph: dict, max_source_fields=120000):
    graph = checked(graph)
    root = root.resolve()
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate source package identity")

    counts, property_families, row_families = Counter(), Counter(), Counter()
    root_counts, field_by_owner = defaultdict(Counter), defaultdict(Counter)
    damage_type_classes = []
    samples = defaultdict(list)
    source_records = []
    native_parents = Counter()

    for package in sorted(nodes):
        root_name = package.split("/", 1)[0]
        if root_name not in ROOTS:
            continue
        records = load(exact_export(root, package, nodes[package]))
        if not isinstance(records, list) or any(not isinstance(x, dict) for x in records):
            raise ValueError("Malformed indexed package: " + package)
        root_counts[root_name]["packages"] += 1
        generated = [x for x in records if x.get("Type") == "BlueprintGeneratedClass"]
        by_name = Counter(x.get("Name") for x in records if isinstance(x.get("Name"), str))
        for cls in generated:
            name = cls.get("Name")
            if not isinstance(name, str):
                raise ValueError("Unnamed generated class: " + package)
            defaults = by_name["Default__" + name]
            root_counts[root_name]["class_defaults_unique" if defaults == 1 else
                                   "class_defaults_missing_or_ambiguous"] += 1
            ref = cls.get("SuperStruct")
            path = ref.get("ObjectPath") if isinstance(ref, dict) else None
            parent = asset_path(path) if isinstance(path, str) else None
            parent_status = ("indexed_export_present" if parent in nodes else
                             "unexported_blueprint_parent" if parent else
                             "non_blueprint_parent_or_missing")
            if parent_status != "indexed_export_present":
                native_parents[(root_name, parent_status)] += 1
            if root_name == "DamageTypes":
                damage_type_classes.append({
                    "package": package, "package_sha256": nodes[package],
                    "generated_class": name,
                    "saved_default_export_matches": defaults,
                    "parent_package_candidate": parent,
                    "parent_status": parent_status,
                    "runtime_effective": "not_established",
                })
        for obj in records:
            kind = obj.get("Type", "<missing>")
            name = obj.get("Name")
            if not isinstance(kind, str):
                raise ValueError("Malformed object type: " + package)
            if not isinstance(name, str):
                continue
            props = obj.get("Properties") or {}
            if not isinstance(props, dict):
                raise ValueError("Malformed Properties: " + package)
            role = ("saved_default" if name.startswith("Default__") else
                    "component_template" if kind.endswith("Component") else "other")
            if root_name == "Data" and isinstance(obj.get("Rows"), dict):
                rows = obj["Rows"]
                root_counts[root_name]["table_exports"] += 1
                root_counts[root_name]["table_rows"] += len(rows)
                for row_name, data in rows.items():
                    if not isinstance(row_name, str) or not isinstance(data, dict):
                        raise ValueError("Malformed DataTable row in " + package)
                    for field, value in data.items():
                        row_families[(package, field, shape(value))] += 1
                continue
            if role == "other" and root_name != "DamageTypes":
                continue
            for field, value in sorted(props.items()):
                if not isinstance(field, str):
                    raise ValueError("Malformed property field in " + package)
                if not field_relevant(field, root_name):
                    continue
                counts["saved_field_occurrences"] += 1
                if counts["saved_field_occurrences"] > max_source_fields:
                    raise ValueError("Source field inventory exceeded bound")
                family = (root_name, role, kind, field, shape(value))
                property_families[family] += 1
                root_counts[root_name]["field_occurrences"] += 1
                field_by_owner[(root_name, role)][field] += 1
                if len(samples[family]) < 2:
                    samples[family].append({"package": package, "record": name,
                                            "package_sha256": nodes[package]})
                nested = (sorted(value) if isinstance(value, dict) else
                          sorted(set().union(*(set(e) for e in value if isinstance(e, dict))))
                          if isinstance(value, list) else [])
                source_records.append({
                    "package": package, "package_sha256": nodes[package],
                    "record": name, "export_type": kind, "role": role,
                    "field": field, "shape": shape(value),
                    "saved_field_value_sha256": source_hash(value),
                    "nested_saved_keys": nested,
                    "runtime_effective": "not_established",
                })
    families = [{
        "root": root_name, "role": role, "export_type": kind,
        "field": field, "shape": kind_shape, "count": n,
        "examples": samples[(root_name, role, kind, field, kind_shape)],
    } for (root_name, role, kind, field, kind_shape), n in property_families.items()]
    families.sort(key=lambda v: (-v["count"], v["root"], v["role"],
                                 v["export_type"], v["field"], v["shape"]))
    rows = [{"table_package": p, "field": f, "shape": s, "occurrences": n}
            for (p, f, s), n in sorted(row_families.items())]
    source_records.sort(key=lambda r: (r["package"], r["record"], r["field"]))
    return {
        "schema_version": 1, "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "review_only_calculator_field_source_surface",
        "safe_for_unattended_publication": False,
        "coverage": {
            "roots": {k: dict(sorted(v.items())) for k, v in sorted(root_counts.items())},
            "field_shape_families": len(families),
            "source_field_records": len(source_records),
            "native_or_unresolved_parent_status": [
                {"root": k[0], "status": k[1], "count": v}
                for k, v in sorted(native_parents.items())],
            "field_names_by_root_and_role": [
                {"root": k[0], "role": k[1],
                 "fields": dict(sorted(v.items()))}
                for k, v in sorted(field_by_owner.items())],
        },
        "damage_type_class_source_identities": damage_type_classes,
        "field_shape_families": families,
        "table_row_field_shapes": rows,
        "source_field_records": source_records,
        "limitations": [
            "Source package taxonomy is not combat class taxonomy.",
            "Presence and value hash of a serialized field do not prove runtime-effective defaults.",
            "DamageTypes class names are not mapped to the human Damage.json matrix.",
            "Native /Script/War code, mitigation formulas and engine inheritance rules are not established.",
            "Array and struct nesting surfaces are names only, not proven compatible types.",
            "No generated source value may write production bot catalogs.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = inspect(args.source_root,
                     json.loads(args.index.read_text(encoding="utf-8")))
    encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
