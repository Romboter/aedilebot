#!/usr/bin/env python3
"""One-command data update: extract the game, fetch War API markers, run every generator, run the adapter tests, write a report.

  python scripts/update_data.py --pak-dir PAK_DIR --work-dir WORK_DIR [--write] [--manifest ACF --build-id N]

PAK_DIR must hold only the vanilla War-WindowsNoEditor.pak (other .pak files are mods and would be mounted too).
WORK_DIR is scratch outside the repo; raw game exports stay there and are never committed.
Without --write the generators only print their spot checks and data/ is not touched.
The report (WORK_DIR/report.md) lists the changed data files and the generator output.
Run it from the repo root. Needs dotnet 10, python 3 and node (for the adapter tests).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR = ROOT / "tools" / "cue4parse-extractor" / "Extractor.csproj"
WARAPI = "https://war-service-live.foxholeservices.com/api/worldconquest/maps"
PAK = "War-WindowsNoEditor.pak"
# generator -> which inputs it takes (S = stats dir, B = blueprint dir). Both come from the same export.
GENERATORS = {
    "gen_vehicles": "SB", "gen_structures": "SB", "gen_aircraft_parts": "SB", "gen_emplacements": "SB",
    "gen_tripods": "SB", "gen_weapons_layout": "SB", "gen_damage": "S", "gen_bunker_pieces": "S",
}


def run(cmd: list[str], cwd: Path = ROOT) -> str:
    print("$", " ".join(str(c) for c in cmd), flush=True)
    cmd = [shutil.which(str(cmd[0])) or str(cmd[0]), *cmd[1:]]  # npx is npx.cmd on Windows
    p = subprocess.run([str(c) for c in cmd], cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    out = p.stdout + p.stderr
    if p.returncode:
        sys.exit(f"FAILED ({p.returncode}): {' '.join(str(c) for c in cmd)}\n{out[-3000:]}")
    return out


def check_inputs(pak_dir: Path, manifest: Path | None, build_id: str | None) -> None:
    paks = sorted(p.name for p in pak_dir.iterdir() if p.suffix.lower() == ".pak")
    if paks != [PAK]:
        sys.exit(f"{pak_dir} must contain only {PAK} (mods get mounted too); found {paks}")
    if manifest or build_id:
        if not (manifest and build_id):
            sys.exit("--manifest and --build-id go together")
        m = re.search(r'"buildid"\s+"(\d+)"', manifest.read_text(encoding="utf-8"))
        if not m or m.group(1) != build_id:
            sys.exit(f"build id mismatch: manifest {m.group(1) if m else None}, expected {build_id}; not updating")


def fetch_warapi(dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    get = lambda url: json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "aedilebot-data-update"}), timeout=60))
    hexes = get(WARAPI)
    for h in hexes:
        (dest / f"{h}.json").write_text(json.dumps(get(f"{WARAPI}/{h}/static")), encoding="utf-8")
    return len(hexes)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pak-dir", type=Path, required=True)
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--write", action="store_true", help="write data/ (default: dry run)")
    ap.add_argument("--manifest", type=Path, help="Steam appmanifest_505460.acf, to check the build id")
    ap.add_argument("--build-id")
    ap.add_argument("--skip-tests", action="store_true")
    a = ap.parse_args()

    work = a.work_dir.resolve()
    if ROOT in [work, *work.parents]:
        sys.exit("--work-dir must be outside the repo: it holds raw game exports")
    check_inputs(a.pak_dir, a.manifest, a.build_id)
    pak = a.pak_dir / PAK
    before = pak.stat()

    export, actors, static = work / "export", work / "actors.json", work / "warapi"
    report = ["# Data update report", ""]

    run(["dotnet", "build", EXTRACTOR, "-c", "Release", "--nologo", "-clp:ErrorsOnly", "-p:NuGetAudit=false"])
    dll = EXTRACTOR.parent / "bin" / "Release" / "net10.0" / "Extractor.dll"
    report.append("- " + run(["dotnet", dll, a.pak_dir, export, "blueprints"]).strip().splitlines()[-1])
    report.append("- " + run(["dotnet", dll, a.pak_dir, actors, "all"]).strip().splitlines()[-1])
    report.append(f"- War API: {fetch_warapi(static)} hexes fetched")

    flag = ["--write"] if a.write else []
    for name, inputs in GENERATORS.items():
        paths = [export] * len(inputs)  # one export serves as both the stats dir and the blueprint dir
        out = run([sys.executable, "-I", ROOT / "scripts" / f"{name}.py", *paths, *flag])
        report += ["", f"## {name}", "```", out.strip(), "```"]
    out = run([sys.executable, "-I", ROOT / "scripts" / "gen_locations.py", actors, static, *flag])
    report += ["", "## gen_locations", "```", out.strip(), "```"]

    if (pak.stat().st_ino, pak.stat().st_size, pak.stat().st_mtime) != (before.st_ino, before.st_size, before.st_mtime):
        sys.exit("PAK changed during the run; aborting")

    if not a.skip_tests:
        out = run(["npx", "vitest", "run"], cwd=ROOT / "bot-ts")
        report += ["", "## Adapter and bot tests", "```", "\n".join(out.strip().splitlines()[-6:]), "```"]

    changed = run(["git", "status", "--short", "--", "data"]).strip()
    report += ["", "## Changed data files" if a.write else "## Dry run: data/ untouched", "```", changed or "(none)", "```"]
    (work / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"report: {work / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
