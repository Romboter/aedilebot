#!/usr/bin/env python3
"""Join serialized component keys to parent SCS nodes; not runtime CDO proof."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.pair_inheritable_component_records import pair_records
from scripts.triage_blueprint_inheritance_exceptions import exact_export
from scripts.resolve_blueprint_weapons import load


def valid(value):
    return isinstance(value, str) and bool(value) and value != "None"


def resolve(root: Path, graph: dict):
    graph = checked(graph)
    root = root.resolve()
    nodes = {x["package"]: x["sha256"] for x in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate indexed packages")
    cache = {}

    def exports(name):
        if name not in nodes:
            raise ValueError("Missing indexed parent " + name)
        if name not in cache:
            data = load(exact_export(root, name, nodes[name]))
            if not isinstance(data, list):
                raise ValueError("Invalid export list " + name)
            cache[name] = data
        return cache[name]

    findings, counts = [], Counter()
    for pair in pair_records(graph)["records"]:
        child, owner, template = pair["source_package"], pair["owner_class"], pair["component_template"]
        handlers = [x for x in exports(child) if x.get("Type") == "InheritableComponentHandler"
                    and x.get("Name") == pair["source_record"]]
        if len(handlers) != 1:
            raise ValueError("Ambiguous handler " + child)
        records = (handlers[0].get("Properties") or {}).get("Records")
        i = pair["record_index"]
        if not isinstance(records, list) or i >= len(records) or not isinstance(records[i], dict):
            raise ValueError("Indexed handler record missing " + child)
        record = records[i]
        key = record.get("ComponentKey")
        if not isinstance(key, dict):
            raise ValueError("Malformed handler key " + child)
        if owner and key.get("OwnerClass", {}).get("ObjectPath") != owner["object_path"]:
            raise ValueError("Owner indexed reference changed")
        if template and record.get("ComponentTemplate", {}).get("ObjectPath") != template["object_path"]:
            raise ValueError("Template indexed reference changed")
        name, guid = key.get("SCSVariableName"), key.get("AssociatedGuid")
        counts_for_key, match, guid_only_diagnostic = {}, None, None
        if not owner or owner["target_export_status"] != "exported":
            status = "owner_not_exported"
        elif not template or template["target_export_status"] != "exported":
            status = "template_not_exported"
        elif not valid(name) or not valid(guid):
            status = "invalid_component_key"
        else:
            pkg = owner["target_package"]
            candidates = [x for x in exports(pkg) if x.get("Type") == "SCS_Node"]
            for x in candidates:
                if not isinstance(x.get("Properties"), dict):
                    raise ValueError("Malformed parent node " + pkg)
            by_name = [x for x in candidates if x["Properties"].get("InternalVariableName") == name]
            by_guid = [x for x in candidates if x["Properties"].get("VariableGuid") == guid]
            exact = [x for x in by_name if x["Properties"].get("VariableGuid") == guid]
            counts_for_key = {"name": len(by_name), "guid": len(by_guid), "exact": len(exact)}
            if len(by_guid) == 1 and not exact:
                guid_only_diagnostic = {
                    "parent_package": pkg,
                    "parent_sha256": nodes[pkg],
                    "parent_scs_node_record": by_guid[0].get("Name"),
                    "parent_saved_variable_name": by_guid[0]["Properties"].get("InternalVariableName"),
                    "child_saved_key_name": name,
                    "confidence": "unverified_guid_only_candidate",
                    "accepted_as_exact_match": False,
                }
            if len(exact) == 1 and valid(exact[0].get("Name")):
                status = "unique_serialized_key_match"
                match = {
                    "parent_package": pkg,
                    "parent_sha256": nodes[pkg],
                    "scs_node_record": exact[0]["Name"],
                    "parent_template": exact[0]["Properties"].get("ComponentTemplate"),
                    "key_sha256": hashlib.sha256((name + "\0" + guid).encode()).hexdigest(),
                }
            elif len(exact) > 1:
                status = "ambiguous_exact_key"
            elif by_name or by_guid:
                status = "name_guid_disagreement"
            else:
                status = "no_parent_scs_match"
        counts[status] += 1
        findings.append({
            "child": child, "source_sha256": pair["source_sha256"],
            "handler_record": pair["source_record"], "record_index": i,
            "owner_class": owner, "child_template": template,
            "status": status, "candidate_counts": counts_for_key,
            "parent_scs_match": match, "guid_only_diagnostic": guid_only_diagnostic,
            "original_property_types": "not_independently_verified",
            "effective_runtime_component": "not_established",
        })
    return {
        "schema_version": 1,
        "source_build_id": graph["source_build_id"],
        "relation_digest": graph["relation_digest"],
        "status": "review_only_serialized_scs_key_matches",
        "safe_for_unattended_publication": False,
        "coverage": {"records": len(findings), "counts": dict(sorted(counts.items()))},
        "records": findings,
        "limitations": [
            "Serialized string equality does not prove original property type or runtime CDO override.",
            "Ambiguous, missing and conflicting node keys remain unresolved.",
            "No inferred selected ammunition, mounted weapon or damage.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    report = resolve(a.source_root, json.loads(a.index.read_text(encoding="utf-8")))
    result = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if a.output:
        a.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
