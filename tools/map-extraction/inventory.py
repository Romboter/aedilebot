"""Diagnostic inventory of CUE4Parse map exports.

This does NOT produce validated Locations.csv entries. The current third-party
exporter may omit placement-only Blueprint actors (e.g., ArrowComponents).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_map(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or not isinstance(data.get("blueprints"), dict):
        raise ValueError(f"{path.name}: expected a CUE4Parse export with a 'blueprints' object")

    blueprints = data["blueprints"]
    if not all(isinstance(name, str) and isinstance(instances, list) for name, instances in blueprints.items()):
        raise ValueError(f"{path.name}: invalid blueprints schema")

    # These are only *diagnostic* candidate counts: no structure classification,
    # world-coordinate conversion or location-name matching is implied.
    relic_classes = {name: len(instances) for name, instances in blueprints.items()
                     if "relicbase" in name.lower()}
    town_classes = {name: len(instances) for name, instances in blueprints.items()
                    if "townbase" in name.lower()}
    return {
        "map": path.stem,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "blueprint_classes": len(blueprints),
        "relic_candidate_count": sum(relic_classes.values()),
        "town_candidate_count": sum(town_classes.values()),
        "relic_classes": relic_classes,
        "town_classes": town_classes,
    }


def make_inventory(input_dir: Path, previous: dict | None = None) -> dict:
    paths = sorted(input_dir.glob("*.json"))
    if not paths:
        raise ValueError(f"No map JSON files found in {input_dir}")
    maps = [inventory_map(path) for path in paths]
    old = {entry["map"]: entry["sha256"] for entry in (previous or {}).get("maps", [])}
    current = {entry["map"]: entry["sha256"] for entry in maps}
    return {
        "map_count": len(maps),
        "candidate_relic_count": sum(x["relic_candidate_count"] for x in maps),
        "candidate_town_count": sum(x["town_candidate_count"] for x in maps),
        "changed_maps": sorted(name for name, digest in current.items() if old.get(name) != digest),
        "removed_maps": sorted(set(old) - set(current)),
        "maps": maps,
        "warning": "Blueprint-only geometry extractor may omit relic actors; these counts are NOT authoritative.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--exporter-sha", required=True)
    parser.add_argument("--pak", required=True, type=Path)
    args = parser.parse_args()

    state_path = args.state / "last-map-inventory.json"
    previous = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    data = make_inventory(args.input, previous)
    data["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    data["exporter_sha"] = args.exporter_sha
    data["game_app_id"] = 505460
    data["pak_bytes"] = args.pak.stat().st_size

    args.output.mkdir(parents=True, exist_ok=True)
    args.state.mkdir(parents=True, exist_ok=True)
    report = args.output / "map-inventory.json"
    report.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (args.output / "map-inventory.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "map", "sha256", "bytes", "blueprint_classes", "relic_candidate_count", "town_candidate_count"])
        writer.writeheader()
        for entry in data["maps"]:
            writer.writerow({key: entry[key] for key in writer.fieldnames})
    shutil.copyfile(report, state_path)
    print(f"Scanned {data['map_count']} map exports; "
          f"{data['candidate_relic_count']} relic and "
          f"{data['candidate_town_count']} town Blueprint candidates.")
    print("WARNING: counts are diagnostic; no Locations.csv changes have been made.")


if __name__ == "__main__":
    main()
