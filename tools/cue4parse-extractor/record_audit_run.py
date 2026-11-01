#!/usr/bin/env python3
"""Record a private read-only Foxhole audit with provenance and conservative drift.

Only hashes, limited comparison findings, and source/version metadata are stored.
The game PAK and raw exported DataTables are never copied into the audit state.
A missing Steam appmanifest is reported as unknown, never invented.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat

SAFE_RUN_KEY = re.compile(r"^[0-9]+-[0-9]+$")
STEAM_BUILD_RE = re.compile(r'"buildid"\s+"([0-9]+)"', re.IGNORECASE)
TABLE_ROOT = Path("War/Content/Blueprints/Data")
INPUT_FILES = (
    "data/Damage.json", "data/Targets.json", "data/Weapons.json",
    "data/Bunker_piece.json", "data_manual/weapon_multipliers.json",
    "data_manual/target_devname_review_proposals.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def steam_manifest(path: Path | None) -> dict:
    if path is None:
        return {"status": "not_provided", "build_id": None}
    try:
        source = path.read_text(encoding="utf-8")
    except PermissionError:
        return {"status": "not_readable", "build_id": None}
    except FileNotFoundError:
        return {"status": "not_present", "build_id": None}
    match = STEAM_BUILD_RE.search(source)
    if not match:
        return {"status": "build_id_missing", "build_id": None}
    return {"status": "parsed_from_local_appmanifest", "build_id": match.group(1)}


def report_findings(audit: dict) -> dict:
    sections = audit.get("sections")
    if not isinstance(sections, dict) or not sections:
        raise ValueError("Audit is missing comparison sections")
    result = {}
    for name, section in sorted(sections.items()):
        if not isinstance(section, dict):
            raise ValueError("Audit section is malformed: " + name)
        required = ("matched", "mismatched", "unmapped", "not_compared", "details")
        if any(k not in section for k in required):
            raise ValueError("Audit section is missing counters/details: " + name)
        values = {key: section[key] for key in required if key != "details"}
        for k in values:
            if not isinstance(values[k], int) or values[k] < 0:
                raise ValueError("Invalid audit count")
        details = section["details"]
        if not isinstance(details, list):
            raise ValueError("Audit details must be a list")
        if len(details) != sum(values[k] for k in ("mismatched", "unmapped", "not_compared")):
            raise ValueError("Audit counts do not reconcile with finding details: " + name)
        # Only nonmatching derived findings, never raw CUE4Parse export.
        result[name] = {"counts": values, "details": details}
    return result


def safe_state_directory(path: Path):
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("State directory must be owned by current runner and be a directory")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("State directory must not be accessible by group/others")
    else:
        path.mkdir(parents=True, mode=0o700)
    runs = path / "runs"
    if runs.exists() or runs.is_symlink():
        info = runs.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("State runs directory has unsafe ownership or permissions")
    else:
        runs.mkdir(mode=0o700)


def previous_snapshot(state_dir: Path) -> dict | None:
    latest = state_dir / "latest.json"
    if not latest.exists() and not latest.is_symlink():
        return None
    if latest.is_symlink():
        raise ValueError("Refusing to follow symlink for latest state")
    pointer = read_json(latest)
    run_key = pointer.get("run_key")
    if not isinstance(run_key, str) or not SAFE_RUN_KEY.fullmatch(run_key):
        raise ValueError("Invalid latest run key: refusing to reset baseline")
    snapshot_path = state_dir / "runs" / (run_key + ".json")
    if snapshot_path.is_symlink() or not snapshot_path.is_file():
        raise ValueError("Latest snapshot missing or is a symlink")
    if sha256_file(snapshot_path) != pointer.get("sha256"):
        raise ValueError("Latest snapshot digest mismatch: refusing to reset baseline")
    doc = read_json(snapshot_path)
    if doc.get("schema_version") != 1 or doc.get("run_key") != run_key:
        raise ValueError("Incompatible saved state")
    return doc


def finding_index(snapshot: dict) -> dict:
    index = {}
    for section, body in snapshot["audit_findings"].items():
        for item in body["details"]:
            key = (section, item.get("status"), item.get("name"),
                   item.get("field"), item.get("dev_name"))
            ident = json.dumps(key, separators=(",", ":"), ensure_ascii=False)
            if ident in index:
                raise ValueError("Duplicate audit finding identity: " + ident)
            index[ident] = item
    return index


def drift(previous: dict | None, current: dict) -> dict:
    if previous is None:
        return {"status": "baseline_created", "previous_run_key": None,
                "archive_changed": None, "table_changes": [],
                "input_changes": [], "tool_changes": [], "finding_changes": [],
                "finding_changes_total": 0}
    old_files, new_files = previous["tables"], current["tables"]
    table_changes = sorted(k for k in set(old_files) | set(new_files)
                           if old_files.get(k) != new_files.get(k))
    old_inputs, new_inputs = previous["inputs"], current["inputs"]
    input_changes = sorted(k for k in set(old_inputs) | set(new_inputs)
                           if old_inputs.get(k) != new_inputs.get(k))
    tool_changes = sorted(k for k in set(previous["tools"]) | set(current["tools"])
                          if previous["tools"].get(k) != current["tools"].get(k))
    before, after = finding_index(previous), finding_index(current)
    changed = []
    for key in sorted(set(before) | set(after)):
        a, b = before.get(key), after.get(key)
        if a != b:
            changed.append({"identity": json.loads(key), "previous": a, "current": b})
    archive_changed = (previous["archive"]["sha256"] != current["archive"]["sha256"])
    changed_build = previous["steam"].get("build_id") != current["steam"].get("build_id")
    # A changed SHA or source table demands review, even if currently compared values match.
    modified = bool(archive_changed or table_changes or input_changes or tool_changes or changed
                    or changed_build)
    return {"status": "changed_review_required" if modified else "unchanged",
            "previous_run_key": previous["run_key"],
            "archive_changed": archive_changed,
            "steam_build_id_changed": changed_build,
            "table_changes": table_changes,
            "input_changes": input_changes,
            "tool_changes": tool_changes,
            "finding_changes": changed[:50],
            "finding_changes_total": len(changed)}


def make_snapshot(args) -> dict:
    if not SAFE_RUN_KEY.fullmatch(args.run_key):
        raise ValueError("run-key must be numeric GitHub run ID and attempt, e.g. 123-1")
    pak_before = args.pak.stat()
    if not stat.S_ISREG(pak_before.st_mode):
        raise ValueError("PAK must be a regular file")
    pak_digest = sha256_file(args.pak)
    pak_after = args.pak.stat()
    # Fail if SteamCMD is replacing/mutating the PAK while we hash it.
    for field in ("st_ino", "st_size", "st_mtime_ns"):
        if getattr(pak_before, field) != getattr(pak_after, field):
            raise ValueError("PAK changed during hashing; fail closed")
    all_tables = {}
    table_dir = args.stats / TABLE_ROOT
    for path in sorted(table_dir.rglob("*.json")):
        # Use relative asset paths: different subfolders may contain the same filename.
        relative_asset = path.relative_to(table_dir).as_posix()
        all_tables[relative_asset] = {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    if len(all_tables) < 40:
        raise ValueError("Suspiciously incomplete DataTable export")
    inputs = {}
    for relative in INPUT_FILES:
        path = args.source / relative
        inputs[relative] = sha256_file(path)
    audit = read_json(args.audit)
    findings = report_findings(audit)
    return {
        "schema_version": 1,
        "run_key": args.run_key,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "archive": {"file": args.pak.name, "bytes": pak_before.st_size,
                    "sha256": pak_digest},
        "steam": steam_manifest(args.appmanifest),
        "tools": {
            "aedilebot_commit": args.source_sha,
            "cue4parse_commit": args.cue4parse_sha,
            "workflow_commit": args.workflow_sha,
        },
        "tables": all_tables,
        "inputs": inputs,
        "source_table_counts": audit.get("source_table_counts", {}),
        "audit_findings": findings,
        "human_review_required": bool(audit.get("requires_human_review", True)),
    }


def atomic_bytes(path: Path, data: bytes, *, replace: bool):
    # No symlinks, no broad-read. Persistent run files are immutable-by-name.
    if not replace:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        return
    tmp = path.with_name(path.name + ".tmp." + str(os.getpid()))
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8")


def markdown(snapshot: dict, changes: dict) -> str:
    rows = [
        "# Foxhole audit provenance and drift",
        "",
        "| Metadata | Value |",
        "|---|---|",
        f"| Game archive SHA-256 | {snapshot['archive']['sha256']} |",
        f"| Archive bytes | {snapshot['archive']['bytes']} |",
        f"| Steam build ID | {snapshot['steam']['build_id'] or 'unavailable (not verified)'} |",
        f"| Steam manifest status | {snapshot['steam']['status']} |",
        f"| Extractor commit | {snapshot['tools']['aedilebot_commit']} |",
        f"| CUE4Parse commit | {snapshot['tools']['cue4parse_commit']} |",
        f"| Workflow commit | {snapshot['tools']['workflow_commit']} |",
        f"| Hashed DataTables | {len(snapshot['tables'])} |",
        f"| Run ID/attempt | {snapshot['run_key']} |",
        "",
        "## Comparison with previous successful run",
        "",
        f"**Status:** {changes['status']}",
        f"**Previous:** {changes['previous_run_key'] or 'none (first baseline)'}",
        "",
        f"- Game PAK changed: {changes['archive_changed']}",
        f"- Source table files changed: {len(changes['table_changes'])}",
        f"- AedileBot input files changed: {len(changes['input_changes'])}",
        f"- Tool/workflow revisions changed: {len(changes['tool_changes'])}",
        f"- Detailed findings added/removed/modified: {changes['finding_changes_total']}",
        "",
    ]
    if changes["table_changes"]:
        rows.extend(["### Changed game tables", ""])
        rows.extend("- " + table for table in changes["table_changes"][:50])
        rows.append("")
    if changes["input_changes"]:
        rows.extend(["### Changed AedileBot input files", ""])
        rows.extend("- " + filename for filename in changes["input_changes"])
        rows.append("")
    if changes["tool_changes"]:
        rows.extend(["### Changed implementation revisions", ""])
        rows.extend("- " + name for name in changes["tool_changes"])
        rows.append("")
    rows.extend([
        "## Safety and limitations", "",
        "- Game build ID is unknown unless an authorized, readable local Steam appmanifest was supplied.",
        "- File/content changes require human review; matching counts alone never authorize writes.",
        "- Only hash manifests and derived audit discrepancies are stored; raw game assets are not archived here.",
        "- No automatic data update, PR generation, or merge is performed.",
        "",
    ])
    return "\n".join(rows)


def run(args):
    safe_state_directory(args.state)
    prev = previous_snapshot(args.state)
    snapshot = make_snapshot(args)
    changes = drift(prev, snapshot)
    # Validate identities and reports before changing the persistent pointer.
    finding_index(snapshot)
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "provenance.json", snapshot)
    write_json(args.output / "drift.json", changes)
    (args.output / "drift.md").write_text(markdown(snapshot, changes), encoding="utf-8")
    snapshot_bytes = (json.dumps(snapshot, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    dest = args.state / "runs" / (args.run_key + ".json")
    atomic_bytes(dest, snapshot_bytes, replace=False)
    pointer = {"run_key": args.run_key, "sha256": hashlib.sha256(snapshot_bytes).hexdigest()}
    atomic_bytes(args.state / "latest.json",
                 (json.dumps(pointer, sort_keys=True, indent=2) + "\n").encode("utf-8"),
                 replace=True)
    print(markdown(snapshot, changes))
    print("PROVENANCE_COMPLETE: review-only; no production data writes.")
    return changes


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pak", type=Path, required=True)
    p.add_argument("--stats", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--appmanifest", type=Path)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--cue4parse-sha", required=True)
    p.add_argument("--workflow-sha", required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--run-key", required=True)
    run(p.parse_args())


if __name__ == "__main__":
    main()
