#!/usr/bin/env python3
"""Copy/verify the derived Foxhole audit history to an independently mounted volume.

This tool does not mount a destination, transmit data, or schedule itself.
The operator must verify the destination is off-host and independently retained.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys

RUN = re.compile(r"^[0-9]+-[0-9]+\\.json$")
SHA = re.compile(r"^[a-f0-9]{64}$")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_dir(path):
    s = path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise ValueError(f"Unsafe directory permissions/owner: {path}")


def files_in_state(state):
    safe_dir(state)
    runs = state / "runs"
    safe_dir(runs)
    latest = state / "latest.json"
    if latest.is_symlink() or not latest.is_file():
        raise ValueError("Missing or linked latest.json; no baseline may be reconstructed")
    pointer = json.loads(latest.read_text(encoding="utf-8"))
    key = pointer.get("run_key")
    if not isinstance(key, str) or not RUN.fullmatch(key + ".json"):
        raise ValueError("Invalid latest run key")
    if not isinstance(pointer.get("sha256"), str) or not SHA.fullmatch(pointer["sha256"]):
        raise ValueError("Invalid latest digest")
    paths = [latest]
    for entry in sorted(runs.iterdir()):
        if entry.is_symlink() or not entry.is_file() or not RUN.fullmatch(entry.name):
            raise ValueError(f"Unexpected run entry: {entry.name}")
        if entry.stat().st_mode & 0o077:
            raise ValueError(f"Run file is accessible by group/others: {entry.name}")
        obj = json.loads(entry.read_text(encoding="utf-8"))
        if obj.get("schema_version") != 1 or obj.get("run_key") + ".json" != entry.name:
            raise ValueError(f"Invalid audit snapshot: {entry.name}")
        paths.append(entry)
    current = runs / (key + ".json")
    if current not in paths or digest(current) != pointer["sha256"]:
        raise ValueError("Latest snapshot missing or digest mismatch")
    return paths


def verify(backup):
    safe_dir(backup)
    manifest = backup / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("No backup manifest")
    obj = json.loads(manifest.read_text(encoding="utf-8"))
    entries = obj.get("files")
    if obj.get("schema_version") != 1 or not isinstance(entries, dict) or not entries:
        raise ValueError("Invalid backup manifest")
    expected = set(entries) | {"manifest.json"}
    actual = set()
    for root, dirs, files in os.walk(backup, followlinks=False):
        relative_root = Path(root).relative_to(backup)
        for dirname in dirs:
            candidate = Path(root) / dirname
            if candidate.is_symlink():
                raise ValueError("Backup contains linked directory")
        for name in files:
            p = Path(root) / name
            if p.is_symlink() or not p.is_file():
                raise ValueError("Backup contains unsafe file")
            actual.add((relative_root / name).as_posix())
    if actual != expected:
        raise ValueError("Backup file inventory does not match manifest")
    for relative, expected_hash in entries.items():
        p = Path(relative)
        if p.is_absolute() or ".." in p.parts or (relative != "latest.json" and
            (len(p.parts) != 2 or p.parts[0] != "runs" or not RUN.fullmatch(p.name))):
            raise ValueError("Unsafe path in manifest")
        if not isinstance(expected_hash, str) or not SHA.fullmatch(expected_hash):
            raise ValueError("Invalid digest in manifest")
        if digest(backup / p) != expected_hash:
            raise ValueError(f"Backup checksum mismatch: {relative}")
    # Re-check pointer, schema, and history, not only the file hashes.
    files_in_state(backup)
    return len(entries)


def backup(state, destination, backup_id):
    paths = files_in_state(state)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", backup_id):
        raise ValueError("Invalid backup ID")
    safe_dir(destination)
    if state.stat().st_dev == destination.stat().st_dev:
        raise ValueError("Destination is on same filesystem as audit state")
    target = destination / backup_id
    if target.exists() or target.is_symlink():
        raise ValueError("Backup ID already exists; refusing overwrite")
    staging = destination / ("." + backup_id + ".partial-" + str(os.getpid()))
    staging.mkdir(mode=0o700)
    try:
        entries = {}
        for source in paths:
            relative = source.relative_to(state)
            dest = staging / relative
            dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            shutil.copyfile(source, dest, follow_symlinks=False)
            os.chmod(dest, 0o600)
            if digest(dest) != digest(source):
                raise ValueError("Source changed during backup")
            entries[relative.as_posix()] = digest(dest)
        manifest = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                    "files": entries}
        m = staging / "manifest.json"
        m.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(m, 0o600)
        verify(staging)
        os.rename(staging, target)
        verify(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    create.add_argument("--state", type=Path, required=True)
    create.add_argument("--destination", type=Path, required=True)
    create.add_argument("--backup-id", required=True)
    check = sub.add_parser("verify")
    check.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "create":
            target = backup(args.state.resolve(), args.destination.resolve(), args.backup_id)
            print(f"BACKUP_VERIFIED {target}")
        else:
            print(f"BACKUP_VERIFIED files={verify(args.backup)}")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"BACKUP_FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
