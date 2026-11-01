#!/usr/bin/env python3
"""Build a deterministic, read-only index of *explicit* Foxhole Blueprint edges.

There is deliberately no damage calculation, filename-based identity guessing,
Steam access, production-data output, or automatic approval in this program.
This records declarations (not flattened inherited defaults). Consumers must
walk SuperStruct and account for class/seat override semantics separately.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from scripts.find_blueprint_dependencies import direct_edges


TABLES = ("BPAmmoDynamicData", "BPMountDynamicData")
SCHEMA = 1


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(data):
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


def check_name(name):
    return isinstance(name, str) and bool(name) and bool(re.fullmatch(r"[A-Za-z0-9_-]+", name))


def table_data(root):
    tables = {}
    for name in TABLES:
        filename = root / "Data" / (name + ".json")
        if not filename.is_file():
            tables[name] = {"sha256": None, "rows": None}
            continue
        if filename.is_symlink() or not filename.resolve().is_relative_to(root.resolve()):
            raise ValueError("Unsafe DataTable export: " + name)
        blob = filename.read_bytes()
        exported = json.loads(blob)
        if (not isinstance(exported, list) or len(exported) != 1
                or not isinstance(exported[0], dict)
                or not isinstance(exported[0].get("Rows"), dict)):
            raise ValueError("Invalid named game DataTable: " + name)
        tables[name] = {
            "sha256": hashlib.sha256(blob).hexdigest(),
            "rows": exported[0]["Rows"],
        }
    return tables


def build_index(root: Path, build_id: str, max_packages=10000):
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("Blueprint export root is missing")
    if not isinstance(build_id, str) or not build_id.isdecimal():
        raise ValueError("An exact numeric Foxhole build ID is required")
    if max_packages < 1:
        raise ValueError("max_packages must be positive")
    packages = sorted(root.rglob("*.json"))
    if not packages or len(packages) > max_packages:
        raise ValueError("Empty or over-limit Blueprint export set")
    tables = table_data(root)
    nodes, objects, numeric_refs, declarations = [], [], [], []
    names = set()

    def declare(source, source_hash, record, field, value):
        declarations.append({
            "source": source, "source_sha256": source_hash,
            "record": record, "field": field, "value": value,
        })

    def numeric_ref(source, source_hash, record, field, table, value):
        rows = tables[table]["rows"]
        valid = check_name(value)
        # Unreal's FName("None") is an unset identity sentinel. Do not
        # report an unset vehicle seat as a missing weapon DataTable row.
        # Actual serialized NameProperty proof is still required downstream.
        status = ("none_sentinel_candidate" if field == "MountCodeName" and value == "None" else
                  "invalid_identifier" if not valid else
                  "table_unavailable" if rows is None else
                  "row_present" if value in rows else "row_missing")
        # A possible case-only spelling difference is a *diagnostic*, not
        # a source edge. It cannot promote a missing named row to a match.
        case_candidates = []
        if status == "row_missing":
            case_candidates = sorted(
                key for key in rows
                if isinstance(key, str) and key != value and key.casefold() == value.casefold()
            )
        numeric_refs.append({
            "source": source, "source_sha256": source_hash,
            "record": record, "field": field,
            "table": table, "row": value,
            "status": status,
            "table_sha256": tables[table]["sha256"],
            "case_only_spelling_candidates_unverified": case_candidates,
        })

    for file in packages:
        if file.is_symlink() or not file.resolve().is_relative_to(root):
            raise ValueError("Unsafe Blueprint export symlink")
        relative = file.relative_to(root).as_posix()
        package = relative[:-5]
        if not all(check_name(part) for part in package.split("/")):
            raise ValueError("Unsafe Blueprint package name: " + relative)
        if package in names:
            raise ValueError("Duplicate package: " + package)
        names.add(package)
        raw = file.read_bytes()
        if len(raw) > 32 * 1024 * 1024:
            raise ValueError("Single export exceeds 32 MiB inspection cap")
        hash_value = hashlib.sha256(raw).hexdigest()
        exports = json.loads(raw)
        if not isinstance(exports, list):
            raise ValueError("Expected list of exported objects: " + relative)
        nodes.append({"package": package, "sha256": hash_value,
                      "export_count": len(exports)})
        for obj in exports:
            if not isinstance(obj, dict):
                raise ValueError("Invalid object in " + relative)
            record = obj.get("Name")
            if not isinstance(record, str):
                # Some exports may have no name; skip property declarations
                # rather than inventing a stable record identity.
                continue
            props = obj.get("Properties") or {}
            if not isinstance(props, dict):
                raise ValueError("Invalid Properties in " + relative)
            if obj.get("Type") == "VehicleSeatComponent" and "MountCodeName" in props:
                numeric_ref(package, hash_value, record, "MountCodeName",
                            "BPMountDynamicData", props["MountCodeName"])
            if not record.startswith("Default__"):
                continue
            for field in ("CodeName", "ExplosiveCodeName"):
                if field in props:
                    declare(package, hash_value, record, field, props[field])
            for field in ("AmmoName", "CompatibleAmmoCodeName"):
                if field in props:
                    numeric_ref(package, hash_value, record, field,
                                "BPAmmoDynamicData", props[field])
            for field in ("MultiAmmo", "GrenadeMultiAmmo"):
                if field not in props:
                    continue
                value = props[field]
                if not isinstance(value, dict) or not isinstance(value.get("CompatibleAmmoNames"), list):
                    numeric_ref(package, hash_value, record, field, "BPAmmoDynamicData", None)
                    continue
                variants = value["CompatibleAmmoNames"]
                if not variants:
                    numeric_ref(package, hash_value, record, field, "BPAmmoDynamicData", None)
                for i, ammo in enumerate(variants):
                    numeric_ref(package, hash_value, record, f"{field}.CompatibleAmmoNames[{i}]",
                                "BPAmmoDynamicData", ammo)
            if "WeaponConfigs" in props:
                configs = props["WeaponConfigs"]
                if not isinstance(configs, list):
                    raise ValueError("Malformed WeaponConfigs in " + relative)
                for i, config in enumerate(configs):
                    if not isinstance(config, dict):
                        raise ValueError("Malformed WeaponConfigs entry in " + relative)
                    numeric_ref(package, hash_value, record, f"WeaponConfigs[{i}].AmmoCodeName",
                                "BPAmmoDynamicData", config.get("AmmoCodeName"))
                    numeric_ref(package, hash_value, record, f"WeaponConfigs[{i}].WeaponCodeName",
                                "BPMountDynamicData", config.get("WeaponCodeName"))
        for edge in direct_edges(root, file):
            objects.append({
                "source": package, "source_sha256": hash_value,
                "record": edge["record"], "field": edge["field"],
                "object_path": edge["object_path"],
                "target": edge["package"],
            })

    for edge in objects:
        edge["status"] = "exported" if edge["target"] in names else "missing_export"
    nodes.sort(key=lambda n: n["package"])
    objects.sort(key=lambda e: (e["source"], str(e["record"]), e["field"], e["target"]))
    numeric_refs.sort(key=lambda e: (e["source"], e["record"], e["field"], e["table"], str(e["row"])))
    declarations.sort(key=lambda e: (e["source"], e["record"], e["field"]))
    for items, keys in (
        (objects, ("source", "record", "field")),
        (numeric_refs, ("source", "record", "field", "table")),
        (declarations, ("source", "record", "field")),
    ):
        seen = set()
        for item in items:
            key = tuple(item[k] for k in keys)
            if key in seen:
                raise ValueError("Ambiguous duplicate source property: " + str(key))
            seen.add(key)

    object_counts = Counter(e["status"] for e in objects)
    row_counts = Counter(e["status"] for e in numeric_refs)
    kinds = Counter(re.sub(r"\[\d+\]$", "", e["field"]) for e in objects)
    row_kinds = Counter(e["table"] for e in numeric_refs)
    semantic = {
        "objects": [{k: e[k] for k in ("source", "record", "field", "object_path", "target", "status")}
                    for e in objects],
        "rows": [{k: e[k] for k in ("source", "record", "field", "table", "row", "status")}
                 for e in numeric_refs],
        "declarations": [{k: e[k] for k in ("source", "record", "field", "value")}
                         for e in declarations],
    }
    return {
        "schema_version": SCHEMA,
        "source_build_id": build_id,
        "status": "review_only_explicit_source_declarations",
        "safe_for_unattended_publication": False,
        "coverage": {
            "exported_packages": len(nodes),
            "object_references": len(objects),
            "object_reference_status": dict(sorted(object_counts.items())),
            "object_reference_fields": dict(sorted(kinds.items())),
            "numeric_row_references": len(numeric_refs),
            "numeric_row_status": dict(sorted(row_counts.items())),
            "numeric_row_tables": dict(sorted(row_kinds.items())),
            "declared_identifiers": len(declarations),
        },
        "table_exports": {k: {"sha256": v["sha256"], "available": v["rows"] is not None}
                          for k, v in sorted(tables.items())},
        "relation_digest": digest(semantic),
        "packages": nodes,
        "object_references": objects,
        "numeric_row_references": numeric_refs,
        "declarations": declarations,
        "limitations": [
            "Only supported explicit Blueprint fields are indexed; this is not complete game semantics.",
            "Declarations are not flattened through inheritance; readers must honor overrides and SuperStruct.",
            "Named DataTable row presence proves identity of a row, not correctness of gameplay damage rules.",
            "CodeName and ExplosiveCodeName are recorded without guessing a numeric DataTable join.",
            "Native /Script/War defaults and implicit references cannot be inferred from this graph.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--build-id", required=True)
    p.add_argument("--max-packages", type=int, default=10000)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = build_index(args.source_root, args.build_id, args.max_packages)
    output = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
