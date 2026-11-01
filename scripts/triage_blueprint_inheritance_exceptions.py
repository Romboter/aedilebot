#!/usr/bin/env python3
"""Read-only triage of missing mount names and incomplete MultiAmmo declarations.

Only exported SuperStruct ancestry, explicit default properties, and exact
named rows are considered. A child may override a parent's seat/weapon state.
This tool inventories that evidence but NEVER treats a base seat as an active
gun or guesses an ammunition or a numeric damage multiplier.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, deque
from pathlib import Path

from scripts.trace_multi_ammo_field_evidence import collect_nested_field_evidence
from scripts.diff_blueprint_graph import checked
from scripts.find_blueprint_dependencies import asset_path
from scripts.index_blueprint_graph import build_index, table_data
from scripts.resolve_blueprint_weapons import assembled_vehicle, explicit_property, load, sha256


MOUNT_TARGETS = (
    ("Vehicles/BattleTanks/BattleTankBase", "MachineGunnerSeat2_GEN_VARIABLE", "BattleTankMachineGunner"),
    ("Vehicles/FieldWeapons/BPFieldMortarBase", "PassengerSeat1_GEN_VARIABLE", "FieldMortarGunner"),
)
AMMO_TARGETS = (
    "Items/BPATRPGLightCItemComponent",
    "Vehicles/LightTank/BPTrainCombatCarWGunnerComponent",
    "Vehicles/LightTank/BPTrainCombatCarWRearGunnerComponent",
    "Vehicles/MediumTank/BPMediumTank2CGunnerMountComponent",
)


def parent_graph(index):
    parents, children = {}, {}
    for edge in index["object_references"]:
        if edge["field"] != "SuperStruct":
            continue
        child, parent = edge["source"], edge["target"]
        if child in parents and parents[child] != parent:
            raise ValueError("Ambiguous Blueprint SuperStruct parent: " + child)
        parents[child] = parent
        children.setdefault(parent, set()).add(child)
    return parents, children


def lineage(package, parents, nodes, max_depth=64):
    path, seen = [], set()
    current = package
    while True:
        if current in seen or len(path) >= max_depth:
            raise ValueError("Cyclic or excessive Blueprint parent chain: " + package)
        if current not in nodes:
            raise ValueError("Referenced parent Blueprint export missing: " + current)
        seen.add(current)
        path.append({"package": current, "sha256": nodes[current]})
        if current not in parents:
            break
        current = parents[current]
    return path


def descendants(package, children, max_nodes=512):
    """Returns (package, exact SuperStruct path from root) for each descendant."""
    q = deque([(package, [package])])
    seen = set()
    result = []
    while q:
        current, chain = q.popleft()
        if current in seen or len(result) >= max_nodes:
            raise ValueError("Cyclic or oversized reverse inheritance graph: " + package)
        seen.add(current)
        result.append((current, chain))
        for child in sorted(children.get(current, ())):
            q.append((child, chain + [child]))
    return result


def exact_export(root, package, expected_sha):
    path = root / (package + ".json")
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("Missing or unsafe exported package: " + package)
    if sha256(path) != expected_sha:
        raise ValueError("Blueprint source hash differs from indexed export: " + package)
    return path


def ammo_structure(value):
    if value is None:
        return {"status": "explicit_none_or_missing", "option_count": 0, "ammo_options": []}
    if not isinstance(value, dict):
        return {"status": "malformed_non_object", "option_count": 0, "ammo_options": []}
    options = value.get("CompatibleAmmoNames")
    if not isinstance(options, list):
        return {"status": "array_not_in_export", "option_count": 0, "ammo_options": [],
                "exported_field_names": sorted(value)}
    if not options:
        return {"status": "empty_array", "option_count": 0, "ammo_options": []}
    if not all(isinstance(v, str) and v and v != "None" for v in options):
        return {"status": "malformed_ammo_identifiers", "option_count": len(options), "ammo_options": []}
    if len(options) != len(set(options)):
        return {"status": "duplicate_ammo_identifiers", "option_count": len(options), "ammo_options": options}
    return {"status": "explicit_ammo_options", "option_count": len(options), "ammo_options": options}


def class_default(root, package, nodes):
    path = exact_export(root, package, nodes[package])
    objs = load(path)
    defaults = [x for x in objs if str(x.get("Name", "")).startswith("Default__")]
    if len(defaults) != 1:
        raise ValueError("Expected one class default in " + package)
    props = defaults[0].get("Properties") or {}
    if not isinstance(props, dict):
        raise ValueError("Invalid class default fields in " + package)
    return defaults[0]["Name"], props



def component_ammo_declarations(root, reference, nodes):
    """Follow an exact mounted-component ObjectPath; retain unproven modes."""
    if not isinstance(reference, str):
        return {"status": "no_component_object_path", "fields": []}
    package = asset_path(reference)
    if package is None:
        return {"status": "non_blueprint_or_native_component", "object_path": reference, "fields": []}
    if package not in nodes:
        return {"status": "referenced_component_not_exported", "package": package, "fields": []}
    path = exact_export(root, package, nodes[package])
    declarations = []
    for field in ("AmmoName", "CompatibleAmmoCodeName", "MultiAmmo", "GrenadeMultiAmmo"):
        try:
            value, evidence = explicit_property(root, path, (field,))
        except ValueError as error:
            return {"status": "component_inheritance_unresolved",
                    "package": package, "reason": str(error), "fields": []}
        if evidence is None:
            continue
        if field in {"MultiAmmo", "GrenadeMultiAmmo"}:
            shape = ammo_structure(value)
            declarations.append({"field": field, "origin": evidence,
                                 "shape": shape, "numeric_join": "not_attempted"})
        else:
            declarations.append({"field": field, "origin": evidence,
                                 "declared_identifier": value,
                                 "numeric_join": "not_attempted"})
    return {"status": "explicit_component_declarations_only", "package": package,
            "package_sha256": nodes[package], "fields": declarations}


def inspect(root: Path, index: dict, mount_targets=MOUNT_TARGETS,
            ammo_targets=AMMO_TARGETS, max_nodes=512):
    index = checked(index)
    root = root.resolve()
    nodes = {x["package"]: x["sha256"] for x in index["packages"]}
    parents, children = parent_graph(index)
    table = table_data(root)["BPMountDynamicData"]
    if table["sha256"] != index["table_exports"]["BPMountDynamicData"]["sha256"]:
        raise ValueError("Mount DataTable hash differs from graph index")
    mount_rows = table["rows"]
    if mount_rows is None:
        raise ValueError("Mount DataTable not exported")

    mounts = []
    for base, seat_name, missing_mount in mount_targets:
        if base not in nodes:
            raise ValueError("Missing target Blueprint: " + base)
        relevant = []
        for child, chain in descendants(base, children, max_nodes):
            source = exact_export(root, child, nodes[child])
            for item in lineage(child, parents, nodes):
                exact_export(root, item["package"], item["sha256"])
            _, seats, _ = assembled_vehicle(root, source)
            seats = [seat for seat in seats if seat["Name"] == seat_name]
            if len(seats) > 1:
                raise ValueError("Duplicate effective named seat: " + child)
            if not seats:
                relevant.append({"package": child, "chain": chain, "status": "seat_absent"})
                continue
            seat = seats[0]
            fields = seat.get("Properties", {})
            mount = fields.get("MountCodeName")
            origin = seat.get("_field_origins", {}).get("MountCodeName")
            if isinstance(mount, str) and mount != "None":
                status = "named_mount_row_present" if mount in mount_rows else "named_mount_row_missing"
            elif mount is None or mount == "None":
                status = "no_mount_name_declared"
            else:
                status = "invalid_mount_name"
            relevant.append({
                "package": child, "chain": chain,
                "status": status, "mount_code_name": mount,
                "mount_identity_provenance": origin,
                "mount_component_object_path": (
                    fields.get("MountComponent", {}).get("ObjectPath")
                    if isinstance(fields.get("MountComponent"), dict) else None
                ),
                "mounted_component_ammunition": component_ammo_declarations(
                    root,
                    (fields.get("MountComponent", {}).get("ObjectPath")
                     if isinstance(fields.get("MountComponent"), dict) else None),
                    nodes,
                ),
                "effective_mount_is_inherited_from_base": (
                    origin is not None and origin.get("asset") == base + ".json"
                ),
            })
        mounts.append({
            "base_blueprint": base,
            "seat": seat_name,
            "missing_named_mount": missing_mount,
            "base_chain": lineage(base, parents, nodes),
            "descendants": relevant,
            "counts": dict(sorted(Counter(x["status"] for x in relevant).items())),
            "classification": "inheritance_only_review_required",
        })

    ammo = []
    for target in ammo_targets:
        if target not in nodes:
            raise ValueError("Missing target component: " + target)
        ancestry = lineage(target, parents, nodes)
        declared_chain = []
        for item in ancestry:
            source_record, props = class_default(root, item["package"], nodes)
            has_field = "MultiAmmo" in props
            if has_field:
                declared_chain.append({
                    "package": item["package"], "sha256": item["sha256"],
                    "record": source_record, "declaration": ammo_structure(props["MultiAmmo"]),
                })
        members = []
        for child, chain in descendants(target, children, max_nodes):
            child_lineage = lineage(child, parents, nodes)
            nearest = None
            for source in child_lineage:
                name, props = class_default(root, source["package"], nodes)
                if "MultiAmmo" in props:
                    nearest = {"source": source["package"], "source_sha256": source["sha256"],
                               "record": name, **ammo_structure(props["MultiAmmo"])}
                    break
            # A child StructProperty may serialize only changed subfields.
            # Preserve the parent's exported choices as *evidence*, never
            # synthesize a merged runtime struct or choose a default ammo.
            parent_option_evidence = None
            if nearest and nearest["status"] in {
                "explicit_none_or_missing", "empty_array", "array_not_in_export",
            }:
                for source in child_lineage[1:]:
                    record, fields = class_default(root, source["package"], nodes)
                    if "MultiAmmo" not in fields:
                        continue
                    candidate = ammo_structure(fields["MultiAmmo"])
                    if candidate["status"] == "explicit_ammo_options":
                        parent_option_evidence = {
                            "source": source["package"],
                            "source_sha256": source["sha256"],
                            "record": record,
                            "options": candidate["ammo_options"],
                            "status": "unverified_parent_default_candidate",
                            "effective_at_runtime": "not_established",
                        }
                        break
            other_fields = []
            for field in ("AmmoName", "CompatibleAmmoCodeName", "GrenadeMultiAmmo",
                          "ProjectileClass", "ProjectileClasses"):
                for source in child_lineage:
                    _, props = class_default(root, source["package"], nodes)
                    if field in props:
                        other_fields.append({
                            "field": field, "origin": source["package"],
                            "source_sha256": source["sha256"],
                            "present": True,
                        })
                        break
            field_evidence = collect_nested_field_evidence(
                child_lineage, nodes,
                lambda package: class_default(root, package, nodes),
            )
            members.append({
                "package": child, "chain": chain,
                "effective_multi_ammo": nearest if nearest else {"status": "not_exported_in_ancestry"},
                "parent_option_evidence": parent_option_evidence,
                "serialized_multi_ammo_field_evidence": field_evidence,
                "other_explicit_field_evidence": other_fields,
            })
        ammo.append({
            "component": target,
            "ancestry": ancestry,
            "declarations_in_ancestry": declared_chain,
            "subclasses": members,
            "counts": dict(sorted(Counter(m["effective_multi_ammo"]["status"]
                                          for m in members).items())),
            "classification": "explicit_ammo_options_unverified_until_resolved",
        })
    return {
        "schema_version": 1,
        "source_build_id": index["source_build_id"],
        "relation_digest": index["relation_digest"],
        "status": "review_only_inheritance_exception_inventory",
        "safe_for_unattended_publication": False,
        "mount_cases": mounts, "multi_ammo_cases": ammo,
        "limitations": [
            "Reverse SuperStruct links are not proof that a descendant is a spawnable game vehicle.",
            "A matching seat object name identifies exported seat overrides, not runtime gunner behavior.",
            "Null or absent MultiAmmo declaration is not proof of unusable or empty runtime ammunition.",
            "Nested MultiAmmo field evidence lists serialized source candidates only; it cannot reconstruct a runtime CDO.",
            "JSON array shapes do not establish original Unreal tag types; typed inspections remain separate.",
            "No native class defaults, numeric proxy damage, casing guess, or automatic publication.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = inspect(args.source_root, json.loads(args.index.read_text(encoding="utf-8")))
    text = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
