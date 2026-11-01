#!/usr/bin/env python3
"""Audit one Aedile player question against pinned saved Foxhole game exports.

Question: how many BattleTankAmmo (75mm) hits to destroy MediumTankW (Silverhand)?
Never equate a serialized value with an independently proven runtime rule.
Full reports are PRIVATE scratch data; only bounded evidence statuses are logged.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import re


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(path):
    objects = read(path)
    if not isinstance(objects, list):
        raise ValueError(f"{path.name}: missing export array")
    tables = [x["Rows"] for x in objects if isinstance(x, dict) and isinstance(x.get("Rows"), dict)]
    if len(tables) != 1 or any(not isinstance(x, dict) for x in tables[0].values()):
        raise ValueError(f"{path.name}: expected exactly one valid DataTable export")
    return tables[0]


def numeric(value):
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def source_ref(value):
    """Only an explicitly serialized package reference is a candidate."""
    if not isinstance(value, dict) or not isinstance(value.get("ObjectPath"), str):
        return None
    match = re.search(r"War/Content/Blueprints/(DamageTypes/[A-Za-z0-9_/-]+)(?=[.']|$)",
                      value["ObjectPath"])
    return match.group(1) if match else None


def saved_enum(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.startswith("EDamageType::"):
        value = value[len("EDamageType::"):]
    return value if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value) else None


def saved_defaults(source_root, package_prefix):
    folder = source_root / package_prefix
    result = []
    if not folder.is_dir():
        return result
    for path in sorted(folder.rglob("*.json")):
        objects = read(path)
        if not isinstance(objects, list):
            raise ValueError("Unexpected CUE4Parse export shape")
        for obj in objects:
            if not isinstance(obj, dict) or not str(obj.get("Name", "")).startswith("Default__"):
                continue
            props = obj.get("Properties") or {}
            if not isinstance(props, dict):
                raise ValueError("Malformed saved default properties")
            result.append({
                "package": path.relative_to(source_root).with_suffix("").as_posix(),
                "source_sha256": sha256(path.read_bytes()).hexdigest(),
                "name": obj["Name"],
                "properties": props,
            })
    return result


def legacy_hits(weapon, target, matrix):
    damage = numeric(weapon["Damage"])
    health = numeric(target["Health"])
    mitigation = numeric(matrix[weapon["DamageType"]][target["Mitigation Type"]])
    if damage is None or health is None or mitigation is None:
        raise ValueError("Bad human inputs")
    if not (damage > 0 and health > 0 and 0 <= mitigation <= 1):
        raise ValueError("Out-of-range human inputs")
    effective_damage = math.ceil(damage * (1 - mitigation))
    if effective_damage <= 0:
        return None
    return {"human_weapon_devname": weapon["Dev Name"],
            "human_target_devname": target["Dev Name"],
            "human_profile": weapon["DamageType"],
            "human_target_category": target["Mitigation Type"],
            "human_damage": damage, "human_health": health,
            "human_mitigation": mitigation, "legacy_damage_per_hit": effective_damage,
            "legacy_hits_to_kill": math.ceil(health / effective_damage)}


def check(source_root, weapons, targets, damage, build_id):
    if build_id != "26058282":
        raise ValueError("Use only the established pinned game build")
    name = "Silverhand - Mk. IV (SvH)"
    if "75mm" not in weapons or name not in targets:
        raise ValueError("Exact baseline catalog identities missing")
    weapon, target = weapons["75mm"], targets[name]
    old = legacy_hits(weapon, target, damage)
    if old["human_weapon_devname"] != "BattleTankAmmo" or old["human_target_devname"] != "MediumTankW":
        raise ValueError("Changed source identities: reevaluate before running")
    paths = {x: source_root / "Data" / (x + ".json") for x in (
        "BPAmmoDynamicData", "DTDamageProfiles", "BPVehicleDynamicData", "BPStructureDynamicData")}
    if any(not p.is_file() for p in paths.values()):
        raise ValueError("Missing exact DataTable export")
    rows = {name: table(path) for name, path in paths.items()}
    ammo = rows["BPAmmoDynamicData"].get("BattleTankAmmo")
    profiles = rows["DTDamageProfiles"]
    game_vehicle = rows["BPVehicleDynamicData"].get("MediumTankW")
    game_structure = rows["BPStructureDynamicData"].get("MediumTankW")
    if ammo is not None and not isinstance(ammo, dict):
        raise ValueError("Malformed ammo row")
    if game_vehicle is not None and not isinstance(game_vehicle, dict):
        raise ValueError("Malformed vehicle row")
    if game_structure is not None and not isinstance(game_structure, dict):
        raise ValueError("Malformed structure row")
    damage_defaults = saved_defaults(source_root, "DamageTypes")
    target_defaults = saved_defaults(source_root, "Vehicles")
    type_package = source_ref(ammo.get("DamageType")) if ammo else None
    type_candidates = [x for x in damage_defaults if x["package"] == type_package]
    type_candidates = [x for x in type_candidates if x["name"].startswith("Default__")]
    selected_type = type_candidates[0] if len(type_candidates) == 1 else None
    type_enum = saved_enum(selected_type["properties"].get("Type")) if selected_type else None
    profile = profiles.get(type_enum) if type_enum else None
    target_candidates = [x for x in target_defaults
                         if x["properties"].get("CodeName") == "MediumTankW"]
    statuses = {
        "ammo_exact_row": "present" if ammo else "missing",
        "ammo_base_damage_vs_human": (
            "match" if ammo and numeric(ammo.get("Damage")) == old["human_damage"]
            else "mismatch" if ammo and numeric(ammo.get("Damage")) is not None else "unresolved"),
        "ammo_saved_damage_type_ref": "resolved_unique_default" if selected_type else
            "unresolved" if not type_package else "missing_or_ambiguous_default",
        "damage_type_saved_enum": "saved" if type_enum else "missing_or_nonstandard",
        "enum_to_profile_row": "unique_exact" if isinstance(profile, dict) else "unresolved",
        "profile_target_column_vs_human": (
            "match" if isinstance(profile, dict) and
            numeric(profile.get(old["human_target_category"])) == old["human_mitigation"]
            else "mismatch" if isinstance(profile, dict) and
            numeric(profile.get(old["human_target_category"])) is not None else "unresolved"),
        "vehicle_dynamic_exact_row": "present" if game_vehicle else "missing",
        "structure_dynamic_exact_row": "present" if game_structure else "missing",
        "vehicle_saved_codename_defaults": (
            "unique" if len(target_candidates) == 1 else
            "none" if not target_candidates else "ambiguous"),
    }
    health_candidates = []
    for origin, row in (("vehicle_dynamic", game_vehicle), ("structure_dynamic", game_structure)):
        if isinstance(row, dict):
            for field in ("MaxHealth", "Health", "ArmourHealth", "ArmourType"):
                if field in row:
                    health_candidates.append({"origin": origin, "field": field,
                         "value_status": ("human_health_match" if field in ("MaxHealth","Health")
                          and numeric(row[field]) == old["human_health"] else
                          "human_health_mismatch" if field in ("MaxHealth","Health")
                          and numeric(row[field]) is not None else "present_unmapped")})
    for item in target_candidates:
        for field in ("MaxHealth", "Health", "ArmourType", "Tier", "CodeName"):
            if field in item["properties"]:
                value = item["properties"][field]
                health_candidates.append({"origin": "saved_vehicle_default", "field": field,
                    "package": item["package"],
                    "value_status": "human_health_match" if field in ("MaxHealth", "Health") and
                    numeric(value) == old["human_health"] else
                    "human_health_mismatch" if field in ("MaxHealth", "Health") and
                    numeric(value) is not None else "present_unmapped"})
    # These statuses are deliberately narrower than a proven runtime scenario.
    statuses["target_source_health_match"] = (
        "some_saved_source_field" if any(x["value_status"] == "human_health_match"
                                         for x in health_candidates) else "unresolved")
    statuses["target_saved_armour_type_present"] = (
        "yes" if any(x["field"] == "ArmourType" for x in health_candidates) else "no")
    return {
        "schema_version": 1, "source_build_id": build_id,
        "question": "How many 75mm rounds to kill a Silverhand Mk. IV?",
        "safe_for_unattended_publication": False,
        "human_calculator_baseline": old,
        "source_files": {k: sha256(p.read_bytes()).hexdigest() for k,p in paths.items()},
        "source_statuses": statuses,
        "source_candidate_details": {
            "damage_type_package": type_package,
            "saved_damage_type_enum": type_enum,
            "candidate_default_count": len(type_candidates),
            "target_saved_codename_candidates": [{
                "package": x["package"], "default": x["name"], "sha256": x["source_sha256"]}
                for x in target_candidates],
            "health_and_classification_field_statuses": health_candidates,
        },
        "source_field_names": {
            "ammo": sorted(ammo) if ammo else [],
            "vehicle_dynamic": sorted(game_vehicle) if game_vehicle else [],
            "structure_dynamic": sorted(game_structure) if game_structure else [],
        },
        "runtime_rules": {
            "penetration": "unverified",
            "armor_effects": "unverified",
            "rounding": "legacy_calculator_only",
            "hit_chance": "scenario_assumption",
        },
        "answerability": "answerable-with-stated-assumptions",
        "limitations": [
            "Human-source baseline is not proof of live Foxhole shot count.",
            "Saved local Blueprint values may not equal effective inherited native game values.",
            "No proof that armor penetration or runtime damage mechanics use this exact profile.",
            "The Silverhand mounts 40mm and 68mm: 75mm is an incoming projectile here.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--weapons", required=True, type=Path)
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--damage", required=True, type=Path)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    a = parser.parse_args()
    result = check(a.source_root, read(a.weapons), read(a.targets), read(a.damage),
                   a.build_id)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("Build:", result["source_build_id"])
    print("One user question:", result["question"])
    print("Source status summary:", result["source_statuses"])
    print("Saved type profile candidate:", result["source_candidate_details"]["saved_damage_type_enum"])
    print("Target candidate default count:", len(result["source_candidate_details"]["target_saved_codename_candidates"]))
    print("Health/classification source field statuses:", result["source_candidate_details"]["health_and_classification_field_statuses"])
    print("Answerability:", result["answerability"], "(runtime rules unresolved)")
    print("No raw game numeric values, PAK bytes, or full game exports printed.")


if __name__ == "__main__":
    main()
