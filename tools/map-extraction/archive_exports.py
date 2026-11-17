"""Immutable, content-addressed archive of *all* successfully exported map JSON.

The source exporter currently writes processed CUE4Parse JSON, not verified
lossless Unreal object JSON. This archives those bytes exactly as produced,
without selecting/reducing actors. Future full-fidelity exports must use a
separate format identifier and pass coverage tests before being called complete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil

import zstandard as zstd
import uuid
from datetime import datetime, timezone
from pathlib import Path

FORMAT = "fh_map_exporter-processed-json-v1"
GAME_APP_ID = 505460


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / ("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


COMPRESSION_LEVEL = 15  # High-ratio, lossless cold storage. Benchmark real maps before increasing.


def archived_sha256(blob: Path) -> str:
    """Read compressed bytes as a stream; never load a full map into memory."""
    digest = hashlib.sha256()
    with blob.open("rb") as source:
        with zstd.ZstdDecompressor().stream_reader(source) as reader:
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def archive_blob(source: Path, expected_sha: str, root: Path) -> str:
    """Store the exact unmodified JSON bytes as a SHA256-addressed zstd frame."""
    blob_relative = f"blobs/sha256/{expected_sha[:2]}/{expected_sha}.json.zst"
    target = root / blob_relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if archived_sha256(target) != expected_sha:
            raise ValueError(f"Archived blob has a checksum mismatch: {target}")
        return blob_relative

    temporary = target.parent / ("." + target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with source.open("rb") as original, temporary.open("wb") as raw:
            compressor = zstd.ZstdCompressor(level=COMPRESSION_LEVEL, write_checksum=True)
            with compressor.stream_writer(raw, closefd=False) as archive:
                shutil.copyfileobj(original, archive, length=1024 * 1024)
            raw.flush()
            os.fsync(raw.fileno())

        if archived_sha256(temporary) != expected_sha:
            raise ValueError(f"Map changed during archival: {source.name}")
        # Never overwrite a historical blob intentionally. The job serializes
        # runs, and its caller must prevent parallel archive writers.
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return blob_relative

def archive_run(
    input_dir: Path,
    inventory_path: Path,
    archive_root: Path,
    exporter_sha: str,
    pak: Path,
    run_id: str | None = None,
) -> Path:
    input_dir, archive_root = input_dir.resolve(), archive_root.resolve()
    if input_dir == archive_root or input_dir in archive_root.parents or archive_root in input_dir.parents:
        raise ValueError("Archive root and working export directory must be separate")

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    recorded = inventory.get("maps")
    if not isinstance(recorded, list) or not recorded:
        raise ValueError("Inventory contains no map records")
    inputs = sorted(input_dir.glob("*.json"))
    indexed_names = [row["map"] + ".json" for row in recorded]
    if len(indexed_names) != len(set(indexed_names)):
        raise ValueError("Inventory contains duplicate map names")
    if set(indexed_names) != {f.name for f in inputs}:
        raise ValueError("Inventory does not match the complete map export directory")

    records = []
    # Verify *every* source before publishing any new run manifest.
    for row in sorted(recorded, key=lambda r: r["map"]):
        name = row["map"]
        if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in {".", ".."}:
            raise ValueError(f"Invalid map name: {name!r}")
        source = input_dir / f"{name}.json"
        if not source.is_file():
            raise ValueError(f"Missing map: {name}")
        current_sha = hash_file(source)
        if current_sha != row["sha256"] or source.stat().st_size != row["bytes"]:
            raise ValueError(f"Map differs from validated inventory: {name}")
        records.append({
            "name": name,
            "sha256": current_sha,
            "bytes": row["bytes"],
            "source_file": source.name,
        })

    # A complete JSON archive is NOT proof of full actor/property coverage.
    # This flag stays false until the extractor has been proven lossless
    # against original Unreal exports and known relic/town actor instances.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", run_id or "local")[:60]
    manifest_name = f"{timestamp}-{safe_id}-{uuid.uuid4().hex[:8]}.json"
    for row in records:
        row["blob"] = archive_blob(input_dir / row["source_file"], row["sha256"], archive_root)

    run_manifest = {
        "format_version": 1,
        "compression": "zstd",
        "compression_level": COMPRESSION_LEVEL,
        "source_format": FORMAT,
        "full_actor_property_coverage_verified": False,
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "game_app_id": GAME_APP_ID,
        "game_build_id": None,  # Do not invent manifest/build IDs.
        "pak_sha256": hash_file(pak),
        "pak_bytes": pak.stat().st_size,
        "exporter_sha": exporter_sha,
        "map_count": len(records),
        "maps": records,
    }
    manifest = archive_root / "runs" / manifest_name
    atomic_json(manifest, run_manifest)
    # Switch latest *only after* every blob and the manifest are safely written.
    atomic_json(archive_root / "latest.json", {
        "run_manifest": manifest.relative_to(archive_root).as_posix(),
        "recorded_utc": run_manifest["recorded_utc"],
        "map_count": len(records),
    })
    return manifest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--archive-root", type=Path, required=True)
    p.add_argument("--exporter-sha", required=True)
    p.add_argument("--pak", type=Path, required=True)
    p.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID"))
    args = p.parse_args()
    manifest = archive_run(
        args.input, args.inventory, args.archive_root, args.exporter_sha, args.pak, args.run_id
    )
    print(f"Archived all validated maps; immutable manifest: {manifest}")
    print("Archive retains unchanged map JSON without duplicate storage.")
    print("WARNING: source exporter fidelity remains unverified; no production data was changed.")


if __name__ == "__main__":
    main()
