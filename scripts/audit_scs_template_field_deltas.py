#!/usr/bin/env python3
"""Compare explicitly serialized parent/child component-template fields only.

This is *not* effective CDO inheritance, property propagation, or damage.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.diff_blueprint_graph import checked
from scripts.find_blueprint_dependencies import asset_path
from scripts.index_blueprint_graph import canonical
from scripts.resolve_blueprint_weapons import load
from scripts.triage_blueprint_inheritance_exceptions import exact_export


def field_hash(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def analyze(root: Path, graph: dict, identities: dict):
    graph = checked(graph)
    if (identities.get("source_build_id") != graph["source_build_id"]
            or identities.get("relation_digest") != graph["relation_digest"]
            or identities.get("status") != "review_only_qualified_scs_template_source_exports"
            or identities.get("safe_for_unattended_publication") is not False):
        raise ValueError("Unpinned or publishable template-identity inventory")
    nodes = {x["package"]: x["sha256"] for x in graph["packages"]}
    if len(nodes) != len(graph["packages"]):
        raise ValueError("Duplicate indexed package")
    root = root.resolve()
    cache = {}

    def exports(package):
        if package not in nodes:
            raise ValueError("Missing indexed component package")
        if package not in cache:
            data = load(exact_export(root,package,nodes[package]))
            if not isinstance(data,list) or not all(isinstance(x,dict) for x in data):
                raise ValueError("Malformed component export file")
            cache[package]=data
        return cache[package]

    def properties(package,entry):
        if (entry.get("status")!="qualified_source_export_unique"
                or entry.get("source_sha256")!=nodes.get(package)
                or entry.get("package")!=package
                or entry.get("outer_source_provenance",{}).get("status")!="serialized_outer_owner_match"):
            raise ValueError("Unverified component source export identity")
        comps=[x for x in exports(package) if
               x.get("Name")==entry.get("component_name")
               and x.get("Type")==entry.get("component_type")]
        classes=[x for x in exports(package) if
                 x.get("Name")==entry.get("generated_class")
                 and x.get("Type")=="BlueprintGeneratedClass"]
        if len(comps)!=1 or len(classes)!=1:
            raise ValueError("Changed component or class export identity")
        outer=comps[0].get("Outer")
        if (not isinstance(outer,dict)
                or outer.get("ObjectName")!="BlueprintGeneratedClass'"+entry["generated_class"]+"'"
                or asset_path(outer.get("ObjectPath"))!=package):
            raise ValueError("Invalid component outer owner source")
        saved=comps[0].get("Properties",{})
        if not isinstance(saved,dict):
            raise ValueError("Malformed component properties")
        return saved

    result, counts, fields, kinds=[],Counter(),Counter(),Counter()
    for row in identities.get("records",[]):
        child,parent=row["child"],row["parent"]
        if (row.get("child_sha256")!=nodes.get(child)
                or row.get("parent_sha256")!=nodes.get(parent)
                or row.get("effective_runtime_component")!="not_established"):
            raise ValueError("Stale component template pair")
        p=properties(parent,row["parent_component"])
        c=properties(child,row["child_component"])
        counts["source_pairs_inspected"]+=1
        parent_type=row["parent_component"]["component_type"]
        child_type=row["child_component"]["component_type"]
        if parent_type != child_type:
            counts["component_type_changed_no_field_comparison"]+=1
            result.append({
                "child":child,"child_sha256":nodes[child],
                "parent":parent,"parent_sha256":nodes[parent],
                "record_index":row["record_index"],
                "parent_scs_node":row["parent_scs_node"],
                "parent_component_type":parent_type,
                "child_component_type":child_type,
                "comparison_status":"different_component_types_not_compared",
                "effective_runtime_component":"not_established",
            })
            continue
        pnames,cnames=set(p),set(c)
        shared=sorted(pnames&cnames)
        changes=sorted(x for x in shared if field_hash(p[x])!=field_hash(c[x]))
        equal=sorted(set(shared)-set(changes))
        child_only=sorted(cnames-pnames)
        parent_only=sorted(pnames-cnames)
        counts["source_pairs_compared"]+=1
        for kind,items in (("explicit_child_only",child_only),
                           ("explicit_parent_only",parent_only),
                           ("explicit_shared_changed",changes),
                           ("explicit_shared_equal",equal)):
            counts[kind+"_occurrences"]+=len(items)
            for name in items:
                fields[(kind,name)]+=1
        kinds[row["parent_component"]["component_type"]]+=1
        result.append({
            "child":child,"child_sha256":nodes[child],
            "parent":parent,"parent_sha256":nodes[parent],
            "record_index":row["record_index"],
            "parent_scs_node":row["parent_scs_node"],
            "component_type":parent_type,
            "comparison_status":"explicit_saved_fields_only",
            "source_key_proof":row["source_key_proof"],
            "explicit_child_only_fields":child_only,
            "explicit_parent_only_fields":parent_only,
            "explicit_shared_changed_fields":changes,
            "explicit_shared_equal_fields":equal,
            "effective_runtime_component":"not_established",
        })
    if len(result)!=identities.get("coverage",{}).get("source_pairs"):
        raise ValueError("Partial component source-pair coverage")
    return {
        "schema_version":1,"source_build_id":graph["source_build_id"],
        "relation_digest":graph["relation_digest"],
        "status":"review_only_serialized_component_field_deltas",
        "safe_for_unattended_publication":False,
        "coverage":{
            "counts":dict(sorted(counts.items())),
            "component_type_counts":dict(sorted(kinds.items())),
            "field_counts":[{"category":k,"field":f,"occurrences":v}
                            for (k,f),v in sorted(fields.items(),
                                key=lambda x:(-x[1],x[0][0],x[0][1]))],
        },
        "records":result,
        "limitations":[
            "Saved JSON fields are explicit serialized source declarations, NOT reconstructed UE4 runtime properties.",
            "Parent-only field omission in a child does not prove inheritance, deletion, or its effective value.",
            "Equal serialized values do not prove equal gameplay behavior; original UE field tags may require separate inspection.",
            "No selected ammunition, damage formula, numerical damage, or unattended publication.",
        ],
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root",type=Path,required=True)
    p.add_argument("--index",type=Path,required=True)
    p.add_argument("--qualified-exports",type=Path,required=True)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    value=analyze(a.source_root,json.loads(a.index.read_text()),
                  json.loads(a.qualified_exports.read_text()))
    out=json.dumps(value,sort_keys=True,indent=2)+"\n"
    if a.output:
        a.output.write_text(out)
    else:
        print(out,end="")


if __name__=="__main__":
    main()
