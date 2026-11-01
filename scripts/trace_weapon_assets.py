"""Trace explicit weapon/mount/ammo references in exported Foxhole Unreal JSON.

This is a *forensic evidence finder*, NOT a damage generator or verified link
resolver. It reports which asset objects carry references to known ammo/vehicle/
mount identifiers and the exact JSON property paths. Matching multiplier
numbers, file names or substring similarity are NEVER used as evidence.

Accepts raw exported Blueprint JSON (including UnrealExporter lists) and
DataTables. Does not require Steam, a game executable or third-party packages.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterator

# The presence of a meaningful reference property is evidence of an asset
# reference, not automatically evidence of the firing relationship.
REFERENCE_KEYS = (
    "ammo", "weapon", "mount", "turret", "projectile", "item",
    "rowname", "assetpath", "objectname", "objectpath", "classpath",
    "actorclass", "classreference", "blueprint",
)
IDENTIFIER_BOUNDARY = r"[A-Za-z0-9_]"


def identifier_in(value: str, identifier: str) -> bool:
    """Match full Unreal identifier, including inside quoted object references."""
    return re.search(
        rf"(?<!{IDENTIFIER_BOUNDARY}){re.escape(identifier)}(?!{IDENTIFIER_BOUNDARY})",
        value,
        flags=re.IGNORECASE,
    ) is not None


def reference_key(path: tuple[str, ...]) -> bool:
    """Require a reference-bearing property, not an arbitrary name/description."""
    if not path:
        return False
    key = path[-1].lower()
    if any(word in key for word in REFERENCE_KEYS):
        return True
    # A typed Unreal ObjectName/ObjectPath may be inside nested object wrappers.
    return key in {"row", "type"} and any(
        any(word in parent.lower() for word in REFERENCE_KEYS) for parent in path[:-1]
    )


def records(payload: object) -> Iterator[tuple[str, object]]:
    """Yield individual Unreal objects / DataTable rows, not giant file-wide scopes."""
    if isinstance(payload, list):
        for n, obj in enumerate(payload):
            if isinstance(obj, dict) and isinstance(obj.get("Rows"), dict):
                for rowname, row in obj["Rows"].items():
                    yield f"{obj.get('Name', 'DataTable')}:Rows/{rowname}", row
            else:
                if not isinstance(obj, (dict, list)):
                    continue
                ident = (obj.get("Name") or obj.get("ObjectName") or obj.get("Type")) if isinstance(obj, dict) else None
                yield f"{n}:{ident or 'object'}", obj
    elif isinstance(payload, dict):
        if isinstance(payload.get("Rows"), dict):
            for rowname, row in payload["Rows"].items():
                yield f"DataTable:Rows/{rowname}", row
        elif isinstance(payload.get("Exports"), list):
            yield from records(payload["Exports"])
        else:
            ident = payload.get("Name") or payload.get("ObjectName") or "object"
            yield str(ident), payload


def references(
    obj: object,
    identifiers: dict[str, str],
    path: tuple[str, ...] = (),
) -> Iterator[dict[str, str]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from references(value, identifiers, path + (str(key),))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from references(value, identifiers, path + (str(index),))
    elif isinstance(obj, str) and reference_key(tuple(p for p in path if not p.isdigit())):
        for role, identifier in identifiers.items():
            if identifier_in(obj, identifier):
                yield {"role": role, "identifier": identifier, "property": "/".join(path), "value": obj}


def selected_identifiers(
    weapon: str | None, sheet: Path | None, ammo: str | None,
    mount: str | None, vehicle: str | None,
) -> tuple[dict[str, str], dict[str, str]]:
    meta = {}
    if weapon:
        if sheet is None:
            raise ValueError("--weapon requires --weapons-json")
        obj = json.loads(sheet.read_text(encoding="utf-8"))
        if weapon not in obj:
            raise ValueError(f"Weapon not in sheet: {weapon}")
        row = obj[weapon]
        # Only identity fields, not label hints or numeric multiplier proxies.
        ammo = ammo or row.get("Dev Name")
        mount = mount or row.get("Mount Dev Name")
        vehicle = vehicle or row.get("Vehicle Dev Name")
        meta["weapon_name"] = weapon
    ids = {k: str(v) for k, v in [("ammo", ammo), ("mount", mount), ("vehicle", vehicle)] if v}
    if not ids:
        raise ValueError("Supply --weapon with --weapons-json, or an explicit --ammo / --mount / --vehicle")
    return ids, meta


def scan(root: Path, ids: dict[str, str], max_files: int = 100000) -> dict:
    if not root.is_dir():
        raise ValueError(f"Export directory does not exist: {root}")
    seen = 0
    matches = []
    ignored = []
    for source in sorted(root.rglob("*.json")):
        # Restrict by file count to avoid an accidental unbounded crawl.
        if seen >= max_files:
            raise ValueError(f"Reached --max-files limit of {max_files}")
        seen += 1
        try:
            with source.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except (ValueError, UnicodeDecodeError) as exc:
            ignored.append({"file": source.relative_to(root).as_posix(), "reason": f"{type(exc).__name__}: {str(exc)[:140]}"})
            continue

        for record, obj in records(payload):
            found = list(references(obj, ids))
            if found:
                matches.append({
                    "file": source.relative_to(root).as_posix(),
                    "record": record,
                    "references": found,
                    # Co-occurrence in a record does not demonstrate that
                    # the mount fires this ammo; operator must inspect it.
                    "roles_present": sorted({x["role"] for x in found}),
                })

    return {
        "schema_version": 1,
        "status": "evidence_candidates_only_not_verified_weapon_ammo_links",
        "search_ids": ids,
        "scanned_files": seen,
        "invalid_json_files": ignored,
        "matches": matches,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("export_root", type=Path, help="Directory of legally obtained exported Blueprint/DataTable JSON")
    p.add_argument("--weapon", help="Exact weapon display key from Weapons.json")
    p.add_argument("--weapons-json", type=Path, help="Read-only path to data/Weapons.json")
    p.add_argument("--ammo", help="Exact ammo Dev Name")
    p.add_argument("--mount", help="Exact mount Dev Name")
    p.add_argument("--vehicle", help="Exact vehicle Dev Name")
    p.add_argument("--max-files", type=int, default=100000)
    p.add_argument("--output", type=Path, help="Write a private local evidence report instead of printing")
    args = p.parse_args(argv)
    if args.max_files < 1:
        p.error("--max-files must be at least 1")
    ids, meta = selected_identifiers(args.weapon, args.weapons_json, args.ammo, args.mount, args.vehicle)
    report = scan(args.export_root, ids, args.max_files)
    report.update(meta)
    data = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        if args.output.resolve().is_relative_to(Path.cwd().resolve()):
            print("WARNING: report is inside current directory. Do not commit proprietary extracted asset details.")
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
