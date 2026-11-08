"""Generate data/tripods.json from the game export (layout: docs/superpowers/specs/2026-11-08-data-layout-redesign.md).

  gen_tripods.py STATS_DIR BP_DIR            # summary + spot check against data/Targets.json
  gen_tripods.py STATS_DIR BP_DIR --write

Tripod = Blueprints/Structures/BPDeployed<Code>.json (not *Ghost; banners live in Blueprints/Banners and are not tripods).
Health and armour type come from the blueprint, repair cost and cost from BPStructureDynamicData[CodeName], the weapon from the seat's
mount row. Weapon name = the item pickup whose CodeName is the mount code (Typhon, Lamentum, ...), else the blueprint's own name.
data/overlay/tripod_excluded.json lists the two Havoc Charge pieces (a different mechanism, not on the sheet).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_structures import amounts, first, table  # noqa: E402
from gen_vehicles import main_weapon  # noqa: E402
from resolve_vehicle_weapons import ROOT, Blueprints  # noqa: E402

DATA = ROOT / "data"


def build(stats, bp_dir):
    bps = Blueprints(bp_dir)
    mounts = {k.lower(): v for k, v in table(stats, "BPMountDynamicData").items()}
    ammo_rows = {k.lower(): v for k, v in table(stats, "BPAmmoDynamicData").items()}
    grenades = {k.lower(): v for k, v in table(stats, "BPGrenadeDynamicData").items()}
    structs = table(stats, "BPStructureDynamicData")
    excluded = set(json.loads((DATA / "overlay" / "tripod_excluded.json").read_text(encoding="utf-8")))
    pickup_names = {}
    for stem, f in bps.files.items():
        if f.parent.name == "ItemPickups":
            for o in bps.load(stem):
                p = o.get("Properties") or {}
                if p.get("CodeName") and isinstance(p.get("DisplayName"), dict):
                    pickup_names[p["CodeName"].lower()] = p["DisplayName"]["SourceString"]
    out = {}
    for stem, f in sorted(bps.files.items()):
        if f.parent.name != "Structures" or not re.fullmatch(r"bpdeployed\w+", stem) or stem.endswith("ghost"):
            continue
        chain = bps.chain(stem)
        code = first(bps, chain, "CodeName")
        if code in excluded:
            continue
        weapon = main_weapon(bps, chain, mounts, ammo_rows, grenades)
        seats = bps.seats(stem)
        name = pickup_names.get(seats[0][0].lower()) if seats else None
        armour = first(bps, chain, "ArmourType")
        out[code] = {
            "name": name or first(bps, chain, "DisplayName")["SourceString"],
            "armourType": armour.split("::")[-1] if armour else None,
            "health": first(bps, chain, "MaxHealth"),
            "repairCost": structs[code]["RepairCost"],
            "weapon": weapon,
            "cost": amounts(structs[code]["ResourceAmounts"]),
        }
    return out


def check(tripods):
    sheet = [v for v in json.loads((DATA / "Targets.json").read_text(encoding="utf-8")).values() if v["ObjectType"] == "Tripods" and v.get("Name")]
    print(f"{len(tripods)} tripods, sheet has {len(sheet)}")
    gen_names = {t["name"].lower() for t in tripods.values()}
    for v in sheet:
        n = v["Name"].lower()
        hit = [t for t in tripods.values() if t["name"].lower() == n or t["name"].lower().split()[0] in n]
        print(f"  {v['Name']}: health {v['Health']} repair {v.get('Repair Cost') or v.get('RepairCost')} -> " + ("; ".join(f"{t['name']} {t['health']}/{t['repairCost']}" for t in hit) or "NO MATCH"))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    tripods = build(*args)
    check(tripods)
    if "--write" in sys.argv:
        (DATA / "tripods.json").write_text(json.dumps(tripods, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written")


if __name__ == "__main__":
    main()
