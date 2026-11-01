#!/usr/bin/env python3
"""Compare two private Blueprint graph indexes without approving game-data changes.

A patch can change which class supplies a value without changing the resulting
number. Compare typed relationships, row availability and exported package
hashes separately. No Steam access, bot writes or automatic publication.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts.index_blueprint_graph import digest


def checked(graph):
    if not isinstance(graph, dict) or graph.get("schema_version") != 1:
        raise ValueError("Unsupported Blueprint graph index schema")
    if graph.get("safe_for_unattended_publication") is not False:
        raise ValueError("Unexpected graph publication authorization")
    for field in ("source_build_id", "packages", "object_references",
                  "numeric_row_references", "declarations", "table_exports"):
        if field not in graph:
            raise ValueError("Missing graph index field: " + field)
    if not all(isinstance(graph[k], list) for k in
               ("packages", "object_references", "numeric_row_references", "declarations")):
        raise ValueError("Invalid graph index collections")
    if not isinstance(graph["table_exports"], dict):
        raise ValueError("Invalid table export catalog")
    semantic = {
        "objects": [
            {k: edge[k] for k in ("source", "record", "field", "object_path", "target", "status")}
            for edge in graph["object_references"]
        ],
        "rows": [
            {k: edge[k] for k in ("source", "record", "field", "table", "row", "status")}
            for edge in graph["numeric_row_references"]
        ],
        "declarations": [
            {k: edge[k] for k in ("source", "record", "field", "value")}
            for edge in graph["declarations"]
        ],
    }
    if digest(semantic) != graph.get("relation_digest"):
        raise ValueError("Indexed relationship fingerprint differs from content")
    return graph


def catalog(entries, key_fields):
    mapped = {}
    for item in entries:
        key = tuple(item[k] for k in key_fields)
        if key in mapped:
            raise ValueError("Duplicate graph key: " + str(key))
        mapped[key] = item
    return mapped


def compare(old, new):
    old, new = checked(old), checked(new)
    changes = []
    change_counts = Counter()
    categories = (
        ("object_reference", ("source", "record", "field"), "object_references",
         ("object_path", "target", "status")),
        ("numeric_row_reference", ("source", "record", "field", "table"), "numeric_row_references",
         ("row", "status")),
        ("identifier_declaration", ("source", "record", "field"), "declarations",
         ("value",)),
    )
    for family, keys, field, values in categories:
        before = catalog(old[field], keys)
        after = catalog(new[field], keys)
        for identity in sorted(set(before) | set(after)):
            prior, current = before.get(identity), after.get(identity)
            previous = {name: prior[name] for name in values} if prior else None
            latest = {name: current[name] for name in values} if current else None
            if previous == latest:
                continue
            kind = ("added" if prior is None else "removed" if current is None
                    else "changed")
            changes.append({
                "family": family,
                "change": kind,
                "source_identity": dict(zip(keys, identity)),
                "before": previous,
                "after": latest,
                "review_required": True,
            })
            change_counts[family + "_" + kind] += 1

    old_files = catalog(old["packages"], ("package",))
    new_files = catalog(new["packages"], ("package",))
    content_changes = []
    for key in sorted(set(old_files) | set(new_files)):
        o, n = old_files.get(key), new_files.get(key)
        old_hash = o["sha256"] if o else None
        new_hash = n["sha256"] if n else None
        if old_hash != new_hash:
            content_changes.append({
                "package": key[0],
                "change": "added" if not o else "removed" if not n else "contents_changed",
                "old_sha256": old_hash, "new_sha256": new_hash,
                "review_required": True,
            })
    for name in sorted(set(old["table_exports"]) | set(new["table_exports"])):
        before = old["table_exports"].get(name)
        after = new["table_exports"].get(name)
        if before != after:
            content_changes.append({
                "table": name,
                "change": "table_export_changed",
                "before": before, "after": after,
                "review_required": True,
            })
    return {
        "schema_version": 1,
        "status": "review_only_no_automatic_approval",
        "old_build_id": old["source_build_id"],
        "new_build_id": new["source_build_id"],
        "old_relation_digest": old["relation_digest"],
        "new_relation_digest": new["relation_digest"],
        "relationship_changes": changes,
        "package_or_table_content_changes": content_changes,
        "counts": {
            "relationship_changes": len(changes),
            "content_changes": len(content_changes),
            "by_family": dict(sorted(change_counts.items())),
        },
        "requires_human_review": bool(changes or content_changes),
        "safe_for_unattended_publication": False,
        "limitations": [
            "Equal relationship identifiers do not establish equal gameplay mechanics.",
            "Blueprint file content hash changes may be nonsemantic or may contain unindexed gameplay changes.",
            "Only indexed relationship types are compared; native code and unmapped fields require separate review.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = compare(json.loads(args.before.read_text(encoding="utf-8")),
                     json.loads(args.after.read_text(encoding="utf-8")))
    result = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
