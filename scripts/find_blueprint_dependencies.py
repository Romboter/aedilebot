#!/usr/bin/env python3
"""List missing exported Blueprint packages for the reference types we resolve.

This is a read-only, restricted dependency *discovery* step. It does not
download assets or assume an ObjectPath ending in .0/.1 is a file path.
The private runner may use these exact package paths with its own extractor.
Only edges understood by the weapon resolvers are considered here.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

PREFIX = "War/Content/Blueprints/"
DEFAULT_SINGLE_REF_FIELDS = ("ItemComponentClass", "ProjectileClass", "ExplosionTemplate")
DEFAULT_ARRAY_REF_FIELDS = ("ProjectileClasses", "GrenadeClasses")


def asset_path(object_path):
    if not isinstance(object_path, str) or not object_path.startswith(PREFIX):
        return None
    package = object_path[len(PREFIX):].split(".", 1)[0]
    p = PurePosixPath(package)
    if not package or package.startswith("/") or any(
        part in {"", ".", ".."} for part in package.split("/")
    ) or "\\" in package or not all(part.replace("_", "").replace("-", "").isalnum() for part in p.parts):
        raise ValueError("Unsafe Blueprint package reference")
    return p.as_posix()


def direct_edges(root, source):
    raw = source.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    objects = json.loads(raw.decode("utf-8"))
    if not isinstance(objects, list):
        raise ValueError("Expected list of exported objects in " + source.name)
    for item in objects:
        if not isinstance(item, dict):
            continue
        cls = item.get("Type")
        props = item.get("Properties")
        props = props if isinstance(props, dict) else {}
        links = []
        if cls == "BlueprintGeneratedClass":
            links.append(("SuperStruct", item.get("SuperStruct")))
        if cls == "VehicleSeatComponent":
            links.append(("MountComponent", props.get("MountComponent")))
        if cls == "InheritableComponentHandler":
            records = props.get("Records", [])
            if not isinstance(records, list):
                raise ValueError("Invalid component records")
            for i, entry in enumerate(records):
                if not isinstance(entry, dict):
                    raise ValueError("Invalid component record")
                key = entry.get("ComponentKey", {})
                if not isinstance(key, dict):
                    raise ValueError("Invalid component key")
                links.append((f"Records[{i}].ComponentKey.OwnerClass", key.get("OwnerClass")))
                links.append((f"Records[{i}].ComponentTemplate", entry.get("ComponentTemplate")))
        if str(item.get("Name", "")).startswith("Default__"):
            for field in DEFAULT_SINGLE_REF_FIELDS:
                links.append((field, props.get(field)))
            for field in DEFAULT_ARRAY_REF_FIELDS:
                value = props.get(field)
                if value is None:
                    continue
                if not isinstance(value, list):
                    raise ValueError(f"Malformed {field} reference array in {source}")
                for index, ref in enumerate(value):
                    links.append((f"{field}[{index}]", ref))
        for field, ref in links:
            value = ref.get("ObjectPath") if isinstance(ref, dict) else None
            target = asset_path(value)
            if target:
                yield {
                    "source_asset": source.relative_to(root).as_posix(),
                    "source_sha256": source_hash,
                    "record": item.get("Name"),
                    "field": field,
                    "object_path": value,
                    "package": target,
                }


def discover(root, max_files=10000):
    if not root.is_dir():
        raise ValueError("Blueprint export root not found")
    export_files = sorted(root.rglob("*.json"))
    if len(export_files) > max_files:
        raise ValueError("Too many exported packages for a single dependency scan")
    edges = []
    for source in export_files:
        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError("Unsafe symlink or exported package path")
        edges.extend(direct_edges(root, source))
    dependencies = sorted({x["package"] for x in edges})
    missing = [x for x in dependencies if not (root / (x + ".json")).is_file()]
    missing_set = set(missing)
    missing_edges = sorted(
        (entry for entry in edges if entry["package"] in missing_set),
        key=lambda entry: (entry["source_asset"], entry["record"] or "", entry["field"], entry["package"]),
    )
    by_type = Counter(re.sub(r"\[\d+\]$", "", entry["field"]) for entry in edges)
    return {
        "schema_version": 1,
        "status": "read_only_dependency_inventory",
        "scanned_packages": len(export_files),
        "explicit_edges": len(edges),
        "resolved_edge_references": len(edges) - len(missing_edges),
        "unresolved_edge_references": len(missing_edges),
        "edge_type_counts": dict(sorted(by_type.items())),
        "missing_source_edges": missing_edges,
        "referenced_packages": len(dependencies),
        "missing_packages": [
            {"package": key, "pak_path": PREFIX + key}
            for key in missing
        ],
        "limitations": [
            "Only explicit SuperStruct, vehicle MountComponent, ItemComponentClass, ProjectileClass, ExplosionTemplate, ProjectileClasses and GrenadeClasses paths are followed.",
            "Missing export is not proof of missing game asset.",
            "Does not resolve native /Script/War class behavior or opaque bytecode links.",
            "Does not infer references using names, values or class prefixes.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("export_root", type=Path)
    p.add_argument("--max-files", type=int, default=10000)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.max_files < 1:
        p.error("--max-files must be positive")
    result = discover(args.export_root, args.max_files)
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
