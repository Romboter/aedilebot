"""Generate data/aircraft_parts.json from the game export (layout: docs/superpowers/specs/2026-11-08-data-layout-redesign.md).

  gen_aircraft_parts.py STATS_DIR BP_DIR            # summary + spot check against data/Targets.json
  gen_aircraft_parts.py STATS_DIR BP_DIR --write

Part row = BPAircraftPartDynamicData (Health, DamagedThreshold = disable level, RepairCost). Armour type and the
aircraft's name come from the aircraft blueprint, found by stripping Engine/Fuselage/Tail/Wing from the part name.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_armour_type import code_names  # noqa: E402
from gen_structures import find, first, table  # noqa: E402
from resolve_vehicle_weapons import ROOT, Blueprints  # noqa: E402

DATA = ROOT / "data"


def build(stats, bp_dir):
    bps = Blueprints(bp_dir)
    codes = code_names(bps)
    out, skipped = {}, []
    for dev, r in table(stats, "BPAircraftPartDynamicData").items():
        part = re.search(r"(Engine|Fuselage|Tail|Wing)$", dev)
        chain = part and find(bps, codes, dev[: part.start()])
        if not chain:
            skipped.append(dev)
            continue
        armour, disp = first(bps, chain, "ArmourType"), first(bps, chain, "DisplayName")
        aircraft = disp["SourceString"] if isinstance(disp, dict) and disp.get("SourceString") else dev[: part.start()]
        out[dev] = {
            "name": f"{aircraft} {part.group(1)}",
            "armourType": armour.split("::")[-1] if armour else None,
            "health": r["Health"],
            "disableLevel": r["DamagedThreshold"],
            "repairCost": r["RepairCost"],
        }
    return out, skipped


def check(parts):
    sheet = {v["Dev Name"]: v for v in json.loads((DATA / "Targets.json").read_text(encoding="utf-8")).values()
             if v["ObjectType"] == "Aircraft_Parts" and v.get("Dev Name")}
    both = [d for d in sheet if d in parts]
    print(f"{len(both)} of {len(sheet)} sheet rows joined")
    for f, g in (("Health", "health"), ("Disable Level", "disableLevel"), ("Repair Cost", "repairCost")):
        print(f"  {f}: {sum(1 for d in both if abs(float(sheet[d][f] or 'nan') - parts[d][g]) < 1e-6)}/{len(both)}")
    print("  Mitigation Type:", sum(1 for d in both if sheet[d]['Mitigation Type'] == parts[d]['armourType']), f"/{len(both)}")
    print("  names equal:", sum(1 for d in both if sheet[d]['Name'] == parts[d]['name']), f"/{len(both)}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    parts, skipped = build(*args)
    print(f"{len(parts)} aircraft parts, skipped: {skipped}")
    check(parts)
    if "--write" in sys.argv:
        (DATA / "aircraft_parts.json").write_text(json.dumps(parts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written")


if __name__ == "__main__":
    main()
