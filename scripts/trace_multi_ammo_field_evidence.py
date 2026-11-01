"""Source-only field provenance for partial serialized MultiAmmo structs.

This intentionally does NOT reconstruct Unreal CDO defaults or runtime arrays.
Only the source package that serialized a nested field and the candidates
higher in the verified SuperStruct chain are represented.
"""
from __future__ import annotations

import hashlib
import json

FIELDS = ("CompatibleAmmoNames", "AmmoSlotFilterAmounts")


def _describe(field, value):
    """Describe the serialized JSON shape; never infer original UE tag types."""
    digest = hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    if not isinstance(value, list):
        return {"shape": "invalid_non_array", "value_sha256": digest}
    result = {"shape": "serialized_array", "count": len(value),
              "value_sha256": digest}
    if field == "CompatibleAmmoNames":
        if not all(isinstance(x, str) and x and x != "None" for x in value):
            result["shape"] = "invalid_name_elements"
        elif len(value) != len(set(value)):
            result["shape"] = "duplicate_names"
        else:
            result["shape"] = "explicit_empty_array" if not value else "explicit_names"
            result["names"] = list(value)
    elif not all(type(x) is int for x in value):
        result["shape"] = "invalid_filter_elements"
    return result


def collect_nested_field_evidence(chain, nodes, load_default):
    """Inspect closest child first, through verified ancestor source exports.

    chain: lineage() entries with package and indexed SHA-256.
    nodes: graph-index package -> SHA-256.
    load_default(package): trusted caller that reads and hash-checks the export,
        returning (default_record_name, properties_dict).

    All field resolution here means *serialized source*, NEVER effective CDO.
    """
    if not chain:
        raise ValueError("Empty MultiAmmo inheritance chain")
    target = chain[0]["package"]
    declarations = {name: [] for name in FIELDS}
    states = []
    for item in chain:
        package = item["package"]
        if package not in nodes or nodes[package] != item["sha256"]:
            raise ValueError("MultiAmmo ancestry/index hash mismatch: " + package)
        record, props = load_default(package)
        if not isinstance(props, dict):
            raise ValueError("Invalid class default properties: " + package)
        if "MultiAmmo" not in props:
            state, struct = "struct_not_serialized", None
        elif props["MultiAmmo"] is None:
            state, struct = "explicit_null_struct", None
        elif not isinstance(props["MultiAmmo"], dict):
            state, struct = "invalid_struct", None
        else:
            state, struct = "serialized_struct", props["MultiAmmo"]
        states.append({"package": package, "sha256": item["sha256"],
                       "record": record, "state": state,
                       "serialized_nested_fields": sorted(struct) if struct is not None else []})
        if struct is None:
            continue
        for field in FIELDS:
            if field not in struct:
                continue
            declarations[field].append({
                "package": package, "sha256": item["sha256"],
                "record": record, "property_path": "MultiAmmo." + field,
                **_describe(field, struct[field]),
            })
    fields = {}
    for field in FIELDS:
        history = declarations[field]
        origin = history[0] if history else None
        if not history:
            resolution = "no_serialized_field_on_chain"
        elif origin["package"] == target:
            resolution = "serialized_on_target"
        else:
            resolution = "unverified_ancestor_candidate"
        if origin and origin["shape"].startswith(("invalid_", "duplicate_")):
            resolution = "invalid_serialized_field"
        # Null/malformed intervening structs cannot be treated as transparent
        # inheritance edges. Preserve historical evidence but flag the block.
        preceding = []
        if origin is not None:
            for item in states:
                if item["package"] == origin["package"]:
                    break
                if item["state"] in {"explicit_null_struct", "invalid_struct"}:
                    preceding.append(item["package"])
        fields[field] = {
            "resolution": resolution,
            "runtime_effective": "not_established",
            "source_declarations_nearest_first": history,
            "opaque_intervening_structs": preceding,
            "type_assertion": "json_shape_only_original_ue_type_requires_independent_inspection",
        }
    return {
        "status": "serialized_field_provenance_only",
        "target": target,
        "source_build_link": "checked_by_caller_graph_index",
        "runtime_effective": "not_established",
        "struct_states_nearest_first": states,
        "fields": fields,
    }
