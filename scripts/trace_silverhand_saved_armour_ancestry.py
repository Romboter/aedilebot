#!/usr/bin/env python3
"""Exact saved Blueprint ancestry of Silverhand mitigation category.

This does NOT assert that native Unreal effective runtime inheritance is proven.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

PREFIX = "War/Content/Blueprints/"
REF = re.compile(r"^War/Content/Blueprints/(Vehicles/[A-Za-z0-9_/-]+)\.[0-9]+$")
LEAF = "Vehicles/MediumTank/BPMediumTankW"


def trace(root: Path, log_text: str, *, leaf=LEAF, expected_category="Tier2Tank"):
    if not log_text:
        raise ValueError("An exact original-property-tag inspection is required")
    tagged = set()
    for line in log_text.splitlines():
        tokens = line.split("\t")
        if len(tokens) == 5 and tokens[0] == "TYPE":
            tagged.add(tuple(tokens[1:]))
    seen = set()
    chain = []
    current = leaf
    boundary = None
    for _ in range(16):
        if current in seen:
            raise ValueError("Cyclic saved Blueprint SuperStruct chain")
        seen.add(current)
        path = root / (current + ".json")
        if not path.is_file():
            boundary = "missing_parent_source"
            break
        exports = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(exports, list):
            raise ValueError("Malformed Blueprint exports")
        generated = [x for x in exports if isinstance(x, dict)
                     and x.get("Type") == "BlueprintGeneratedClass"]
        if len(generated) != 1:
            boundary = "missing_or_ambiguous_generated_class"
            break
        cls = generated[0]
        class_name = cls.get("Name")
        defaults = [x for x in exports if isinstance(x, dict)
                    and x.get("Name") == "Default__" + str(class_name)]
        if len(defaults) != 1:
            boundary = "missing_or_ambiguous_default_export"
            break
        props = defaults[0].get("Properties") or {}
        if not isinstance(props, dict):
            raise ValueError("Malformed saved default")
        if len(chain) == 0 and props.get("CodeName") != "MediumTankW":
            raise ValueError("Wrong target canonical CodeName")
        armour = props.get("ArmourType")
        tag = "EnumProperty" if (
            PREFIX + current + ".uasset", "Default__" + str(class_name),
            "ArmourType", "EnumProperty") in tagged else "unverified"
        chain.append({"package": current, "saved_class": class_name,
                      "default": defaults[0].get("Name"),
                      "source_sha256": sha256(path.read_bytes()).hexdigest(),
                      "explicit_armour_type": armour if isinstance(armour, str) else None,
                      "original_armour_type_tag": tag,
                      "has_saved_armour_type": "ArmourType" in props})
        sup = cls.get("SuperStruct")
        path_string = sup.get("ObjectPath") if isinstance(sup, dict) else None
        match = REF.fullmatch(path_string or "")
        if not match:
            boundary = "native_or_external_parent" if path_string else "no_parseable_saved_parent"
            break
        current = match.group(1)
    else:
        raise ValueError("Bounded parent chain exceeded")
    declarations = [node for node in chain if node["has_saved_armour_type"]]
    target_enum = "EArmourType::" + expected_category
    if len(declarations) != 1:
        status = "missing_or_conflicting_saved_armour_declarations"
    elif declarations[0]["explicit_armour_type"] != target_enum:
        status = "saved_armour_category_disagrees_with_human"
    elif declarations[0]["original_armour_type_tag"] != "EnumProperty":
        status = "saved_category_original_tag_unverified"
    elif boundary != "native_or_external_parent":
        status = "ancestor_chain_unresolved"
    else:
        status = "exact_saved_ancestor_declaration_matches_human"
    return {"schema_version": 1, "leaf": leaf, "chain": chain,
            "saved_source_boundary": boundary,
            "source_status": status, "human_target_category": expected_category,
            "native_effective_inheritance": "unverified",
            "safe_for_unattended_publication": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--inspector-log", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = trace(a.source_root, a.inspector_log.read_text(encoding="utf-8"))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Silverhand saved parent chain:", [node["package"] for node in result["chain"]])
    print("Armour declaration source status:", result["source_status"])
    print("Original ArmourType source tag:", [
        (node["package"],node["original_armour_type_tag"])
        for node in result["chain"] if node["has_saved_armour_type"]])
    print("Native effective inheritance:",result["native_effective_inheritance"])
    print("No numeric game data or raw source exports printed.")


if __name__ == "__main__":
    main()
