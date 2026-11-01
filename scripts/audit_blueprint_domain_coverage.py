#!/usr/bin/env python3
"""Build-fingerprinted, source-only Blueprint domain coverage and gap inventory.

All categories are package-path groupings or lexical candidates, NOT verified
gameplay classes. Full reports remain on the private runner. No runtime CDO,
inheritance default, damage, or weapon-to-building behavior is inferred.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from scripts.audit_blueprint_reference_surface import walk
from scripts.diff_blueprint_graph import checked
from scripts.find_blueprint_dependencies import asset_path
from scripts.triage_blueprint_inheritance_exceptions import exact_export
from scripts.resolve_blueprint_weapons import load


COMBAT_FIELDS = {
    "MountComponent", "ItemComponentClass", "ProjectileClass",
    "ExplosionTemplate", "ProjectileClasses", "GrenadeClasses",
}
COMBAT_ROWS = {
    "AmmoName", "CompatibleAmmoCodeName", "MountCodeName",
    "MultiAmmo", "GrenadeMultiAmmo", "WeaponConfigs",
}
KEYWORDS = (
    "health", "damage", "armor", "armour", "resist", "penetrat",
    "repair", "construct", "build", "bunker", "garrison", "turret",
    "mount", "weapon", "ammo", "projectile", "reload", "range",
    "upgrade", "fire", "explosi", "mitigat",
)
PATH_GROUPS = {
    "Vehicles": "vehicles_path",
    "Structures": "structures_path",
    "Buildings": "structures_path",
    "Bunkers": "structures_path",
    "Defenses": "defenses_path",
    "Emplacements": "defenses_path",
    "Items": "items_path",
    "Projectiles": "projectiles_path",
}


def domain(package):
    """Explicit path grouping only. Unknown roots are retained rather than guessed."""
    return PATH_GROUPS.get(package.split("/", 1)[0], "other_path")


def normalized(path):
    return re.sub(r"\[\d+\]", "[]", path)


def top(counter, limit=30):
    return [{"name": k, "count": v} for k, v in
            sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]]


def scan(root: Path, graph: dict, max_refs=350000):
    graph = checked(graph)
    root = root.resolve()
    nodes = {p["package"]: p["sha256"] for p in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate indexed packages")

    known = {(e["source"], e["record"], e["field"], e["object_path"])
             for e in graph["object_references"]}
    if len(known) != len(graph["object_references"]):
        raise ValueError("Duplicate indexed object edges")
    seen_known = set()
    totals, package_roots, exports, components = Counter(), Counter(), Counter(), Counter()
    by_domain = defaultdict(Counter)
    export_by_domain = defaultdict(Counter)
    component_by_domain = defaultdict(Counter)
    cdo_fields = defaultdict(Counter)
    candidate_fields = defaultdict(Counter)
    row_status = defaultdict(Counter)
    reference_family = defaultdict(Counter)
    target_status = defaultdict(Counter)
    candidates = Counter()
    examples = defaultdict(list)

    # Exact graph statuses are not effective game behavior. Preserve that boundary.
    for edge in graph["numeric_row_references"]:
        group = domain(edge["source"])
        status = edge["status"]
        field = normalized(edge["field"])
        row_status[(group, field)][status] += 1
        if status == "row_present" and any(field.startswith(x) for x in COMBAT_ROWS):
            by_domain[group]["indexed_exact_row_present_source_only"] += 1
    for edge in graph["object_references"]:
        group = domain(edge["source"])
        target_status[group][edge["status"]] += 1
        if edge["status"] == "exported" and (edge["field"] in COMBAT_FIELDS or
                edge["field"].split("[", 1)[0] in COMBAT_FIELDS):
            by_domain[group]["indexed_combat_reference_export_present_source_only"] += 1

    for package in sorted(nodes):
        group = domain(package)
        package_roots[package.split("/", 1)[0]] += 1
        by_domain[group]["packages"] += 1
        objects = load(exact_export(root, package, nodes[package]))
        if not isinstance(objects, list) or not all(isinstance(o, dict) for o in objects):
            raise ValueError("Malformed exact exported objects: " + package)
        generated = [o["Name"] for o in objects
                     if o.get("Type") == "BlueprintGeneratedClass"
                     and isinstance(o.get("Name"), str)]
        names = Counter(o.get("Name") for o in objects if isinstance(o.get("Name"), str))
        by_domain[group]["generated_classes"] += len(generated)
        for cls in generated:
            match = names["Default__" + cls]
            by_domain[group]["generated_class_with_one_saved_default" if match == 1
                             else "generated_class_without_unique_saved_default"] += 1
        lowered = package.lower()
        for token in ("weapon", "ammo", "projectile", "garrison", "bunker",
                      "pillbox", "turret", "defense", "defence", "emplacement"):
            if token in lowered:
                candidates[(group, token)] += 1

        for obj in objects:
            typ = obj.get("Type", "<missing>")
            if not isinstance(typ, str):
                typ = "<malformed>"
            exports[typ] += 1
            export_by_domain[group][typ] += 1
            by_domain[group]["exported_objects"] += 1
            if typ.endswith("Component"):
                components[typ] += 1
                component_by_domain[group][typ] += 1
            name = obj.get("Name")
            props = obj.get("Properties") or {}
            if not isinstance(props, dict):
                raise ValueError("Malformed source Properties: " + package)
            if isinstance(name, str) and name.startswith("Default__"):
                for field in props:
                    cdo_fields[group][field] += 1
            if group in ("structures_path", "defenses_path"):
                for field in props:
                    if any(hint in field.lower() for hint in KEYWORDS):
                        candidate_fields[(group, typ)][field] += 1

            for field, value in walk(obj):
                totals["objectpath_occurrences"] += 1
                if totals["objectpath_occurrences"] > max_refs:
                    raise ValueError("ObjectPath inventory exceeds scan bound")
                short = field.removeprefix("Properties.")
                target = asset_path(value) if isinstance(value, str) else None
                key = (package, name, short, value)
                status = ("invalid_objectpath" if not isinstance(value, str) or not value else
                          "indexed_exact" if target and key in known else
                          "unindexed_blueprint" if target else "native_or_external")
                if status == "indexed_exact":
                    seen_known.add(key)
                totals[status] += 1
                by_domain[group][status] += 1
                family = (group, typ, normalized(field))
                reference_family[family][status] += 1
                if status == "unindexed_blueprint" and len(examples[family]) < 2:
                    examples[family].append({
                        "package": package, "source_sha256": nodes[package],
                        "record": name, "field": field, "target": target,
                    })
    if seen_known != known:
        raise ValueError("Indexed source object references absent from exact exports")

    families = []
    for (group, typ, field), statuses in reference_family.items():
        if statuses["unindexed_blueprint"] == 0:
            continue
        families.append({
            "domain": group, "export_type": typ, "field": field,
            "unindexed_blueprint": statuses["unindexed_blueprint"],
            "indexed_exact": statuses["indexed_exact"],
            "examples": examples[(group, typ, field)],
        })
    families.sort(key=lambda f: (-f["unindexed_blueprint"],
                                 f["domain"], f["export_type"], f["field"]))

    return {
        "schema_version": 1,
        "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "review_only_source_domain_coverage",
        "safe_for_unattended_publication": False,
        "coverage": {
            "packages": len(nodes),
            "source_object_references_checked": len(seen_known),
            "reference_status_counts": dict(sorted(totals.items())),
            "package_roots": top(package_roots, 60),
            "domains": {k: dict(sorted(v.items())) for k, v in sorted(by_domain.items())},
            "target_export_status_by_domain": {
                k: dict(sorted(v.items())) for k, v in sorted(target_status.items())},
            "export_types": top(exports, 80),
            "component_types": top(components, 80),
            "export_types_by_domain": {k: top(v, 50) for k, v in sorted(export_by_domain.items())},
            "components_by_domain": {k: top(v, 50) for k, v in sorted(component_by_domain.items())},
            "saved_default_fields_by_domain": {
                k: top(v, 90) for k, v in sorted(cdo_fields.items())},
            "structure_defense_candidate_fields": {
                k[0] + "/" + k[1]: top(v, 60)
                for k, v in sorted(candidate_fields.items())},
            "lexical_package_name_candidates": [
                {"path_domain": d, "substring": s, "count": n}
                for (d, s), n in sorted(candidates.items())],
            "row_status_by_domain_and_field": [
                {"domain": d, "field": f, "statuses": dict(sorted(v.items()))}
                for (d, f), v in sorted(row_status.items())],
        },
        "top_unindexed_blueprint_reference_families": families[:80],
        "unindexed_families_total": len(families),
        "limitations": [
            "Path buckets and lexical name matches are discovery aids, not combat class identities.",
            "Reference paths are serialized fields, not necessarily gameplay dependency edges.",
            "Default__ export presence does not establish effective CDO values.",
            "Unindexed references may be Unreal internals; exact target class and owner need verification.",
            "Native class logic and bytecode behavior are not inspected.",
            "Indexed row presence does not prove ammo selection, projectile behavior, or damage.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = scan(args.source_root,
                  json.loads(args.index.read_text(encoding="utf-8")))
    data = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
