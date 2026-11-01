#!/usr/bin/env python3
"""Source-only, pinned-game comparison of DTDamageProfiles with Aedile's human matrix.

Read CUE4Parse JSON in private temporary storage; never print numeric game rows.
This does not establish native runtime mitigation rules or effective inherited defaults.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re


NIXIE_STRUCTURE_FIELDS = ("Tier1Structure", "Tier2Structure", "Tier3Structure")
PREFIX = "War/Content/Blueprints/"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table_rows(path: Path) -> dict:
    exports = load_json(path)
    if not isinstance(exports, list):
        raise ValueError(f"{path.name}: expected export list")
    tables = [x["Rows"] for x in exports if isinstance(x, dict) and isinstance(x.get("Rows"), dict)]
    if len(tables) != 1:
        raise ValueError(f"{path.name}: expected one DataTable export, got {len(tables)}")
    if any(not isinstance(k, str) or not isinstance(v, dict) for k, v in tables[0].items()):
        raise ValueError("DataTable rows must be mappings")
    return tables[0]


def normalize_type_key(value: str) -> str:
    """Nixie-compatible discovery alias ONLY; ambiguous aliases are never joined."""
    value = re.sub(r"^EDamageType::", "", value, flags=re.I)
    value = re.sub(r"DamageType", "", value, flags=re.I)
    return value.strip().lower()


def finite_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (float, int)):
        x = float(value)
    elif isinstance(value, str):
        try:
            x = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return x if x == x and abs(x) != float("inf") else None


def key_matches(source: dict, human: dict):
    # Preserve all candidate sets; no case-folded or normalized tie breaking.
    human_by_alias = {}
    for name in human:
        human_by_alias.setdefault(normalize_type_key(name), []).append(name)
    result = []
    for source_name in source:
        exact = source_name in human
        aliases = sorted(human_by_alias.get(normalize_type_key(source_name), []))
        status = ("exact" if exact else "alias_unique" if len(aliases) == 1
                  else "alias_ambiguous" if aliases else "missing_human")
        result.append((source_name, source_name if exact else aliases[0] if len(aliases) == 1 else None, status))
    return result


def compare_profiles(source: dict, human: dict):
    """Compares raw mitigation fraction and its Nixie-computed complement separately."""
    by_field = {}
    by_row = []
    overall = Counter()
    for source_key, human_key, resolution in key_matches(source, human):
        counts = Counter()
        if human_key is not None:
            for field, value in source[source_key].items():
                if field not in human[human_key]:
                    continue
                src = finite_number(value)
                cur = finite_number(human[human_key][field])
                if src is None or cur is None:
                    counts["nonnumeric_or_missing"] += 1
                    continue
                # Nixie clamps the complement, not the raw value.
                direct = abs(src - cur) <= 1e-7
                complement = abs(max(0.0, 1.0 - src) - cur) <= 1e-7
                outcome = ("both" if direct and complement else "direct_only" if direct
                           else "complement_only" if complement else "neither")
                counts[outcome] += 1
                by_field.setdefault(field, Counter())[outcome] += 1
        overall[resolution] += 1
        overall.update(counts)
        by_row.append({"source_row": source_key, "human_row": human_key,
                       "join": resolution, "field_status_counts": dict(sorted(counts.items()))})
    for key in human:
        if key not in {name for _, name, _ in key_matches(source, human)}:
            overall["human_rows_unmatched"] += 1
    return {
        "counts": dict(sorted(overall.items())),
        "by_field": {name: dict(sorted(c.items())) for name, c in sorted(by_field.items())},
        "by_row": by_row,
    }


def damage_type_references(ammo_rows: dict, damage_exports: dict[str, list]):
    """Inventory saved references and names without asserting runtime-effective defaults."""
    records, counts = [], Counter()
    for ammo_code, row in sorted(ammo_rows.items()):
        raw = row.get("DamageType")
        ref = raw.get("ObjectPath") if isinstance(raw, dict) else None
        package = None
        if isinstance(ref, str):
            match = re.search(r"War/Content/Blueprints/(DamageTypes/[^.']+)", ref)
            if match:
                package = match.group(1)
        packages = damage_exports.get(package, []) if package else []
        status = ("saved_reference_exported" if packages else "saved_reference_missing_export"
                  if package else "unresolved_reference")
        counts[status] += 1
        records.append({"ammo_row": ammo_code, "damage_type_package_candidate": package,
                        "status": status, "matched_exports": len(packages)})
    return records, dict(sorted(counts.items()))


def audit(source_root: Path, human_path: Path, build_id: str):
    if not re.fullmatch(r"[0-9]{6,12}", build_id):
        raise ValueError("Explicit pinned numeric build ID required")
    source_root = source_root.resolve()
    paths = {
        "damage_profiles": source_root / "Data/DTDamageProfiles.json",
        "ammo_dynamic": source_root / "Data/BPAmmoDynamicData.json",
    }
    for label, path in paths.items():
        if not path.is_file() or not path.resolve().is_relative_to(source_root):
            raise ValueError(f"Missing exact {label} file: {path}")
    source = table_rows(paths["damage_profiles"])
    ammo = table_rows(paths["ammo_dynamic"])
    human = load_json(human_path)
    if not isinstance(human, dict) or any(not isinstance(x, dict) for x in human.values()):
        raise ValueError("Human matrix expected object keyed by damage type")
    damage_files = sorted((source_root / "DamageTypes").rglob("*.json"))
    damage_exports = {}
    for path in damage_files:
        rel = path.relative_to(source_root).with_suffix("").as_posix()
        if rel in damage_exports:
            raise ValueError("Duplicate exact damage-type source file")
        objs = load_json(path)
        if not isinstance(objs, list):
            raise ValueError("Damage-type source is not a list of exports")
        damage_exports[rel] = [x.get("Name") for x in objs
                               if isinstance(x, dict) and x.get("Type") == "BlueprintGeneratedClass"]
    comparison = compare_profiles(source, human)
    refs, ref_counts = damage_type_references(ammo, damage_exports)
    columns = Counter(field for row in source.values() for field in row.keys())
    return {
        "schema_version": 1, "source_build_id": build_id,
        "safe_for_unattended_publication": False,
        "provenance": {"pak_extraction": "CUE4Parse, saved export JSON, not native runtime",
                       "source_files": {
                           label: {"sha256": sha256(path.read_bytes()).hexdigest(),
                                   "relative_package": "Data/" + path.stem}
                           for label, path in paths.items()},
                       "human_matrix_sha256": sha256(human_path.read_bytes()).hexdigest()},
        "coverage": {"profile_row_count": len(source), "ammo_row_count": len(ammo),
                     "damage_type_exported_packages": len(damage_exports),
                     "human_matrix_row_count": len(human),
                     "profile_source_field_occurrences": dict(sorted(columns.items())),
                     "nixie_structure_fields_present": {
                         field: columns.get(field, 0) for field in NIXIE_STRUCTURE_FIELDS},
                     "ammo_reference_status_counts": ref_counts},
        "comparison": comparison, "ammo_references": refs,
        "limitations": [
            "Original nested DataTable row property tags not verified by this JSON comparison",
            "Source rows and identifiers do not prove effective runtime default inheritance",
            "Nixie 1-minus-field and authored multiplier are consumer interpretations",
            "Numerical matching cannot independently prove native runtime damage mitigation",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--human-damage", required=True, type=Path)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.source_root, args.human_damage, args.build_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Pinned build", result["source_build_id"])
    print("Profile rows", result["coverage"]["profile_row_count"],
          "Ammo rows", result["coverage"]["ammo_row_count"],
          "DamageType packages", result["coverage"]["damage_type_exported_packages"])
    print("Profile field presence", sorted(result["coverage"]["profile_source_field_occurrences"]))
    print("Source-vs-human comparison", result["comparison"]["counts"])
    print("By-field status", result["comparison"]["by_field"])
    print("Ammo reference statuses", result["coverage"]["ammo_reference_status_counts"])
    print("No numeric game row values or original PAK data emitted; source-only statuses.")


if __name__ == "__main__":
    main()
