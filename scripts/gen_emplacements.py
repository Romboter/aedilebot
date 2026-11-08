"""Generate data/emplacements.json from the game export (layout: docs/superpowers/specs/2026-11-08-data-layout-redesign.md).

  gen_emplacements.py STATS_DIR BP_DIR            # summary + spot check against data/Targets.json
  gen_emplacements.py STATS_DIR BP_DIR --write

Gun = Blueprints/Structures/Emplacements/BPEmplaced<Code>.json (not Rotator/Mount/Gunner/Component). Name, health and the
emplaced modifiers are on the blueprint, repair cost and cost in BPStructureDynamicData[CodeName], the weapon from the seat's mount row.
Emplaced (inside a Trench Emplacement) health = MaxHealth / EmplacedIncomingDamageModifier; Zeal and Bolas have no modifier (x1).
Armour type is not in the export (native-class default): data/overlay/armour_types.json.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_armour_type import code_names  # noqa: E402
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
    armour = json.loads((DATA / "overlay" / "armour_types.json").read_text(encoding="utf-8"))
    out = {}
    for stem, f in sorted(bps.files.items()):
        if f.parent.name != "Emplacements" or not re.fullmatch(r"bpemplaced\w+", stem) or re.search(r"rotator|mount|gunner|component$", stem):
            continue
        chain = bps.chain(stem)
        code = first(bps, chain, "CodeName")
        name = first(bps, chain, "DisplayName")
        mod = first(bps, chain, "EmplacedIncomingDamageModifier")
        row = structs[code]
        health = first(bps, chain, "MaxHealth")
        out[code] = {
            "name": name["SourceString"],
            "armourType": (first(bps, chain, "ArmourType") or "").split("::")[-1] or armour.get(code),
            "health": health,
            "emplaced": {"healthMultiplier": 1 / mod if mod else 1, "trackingMultiplier": first(bps, chain, "EmplacedTrackingModifier") or 1},
            "repairCost": row["RepairCost"],
            "weapon": main_weapon(bps, chain, mounts, ammo_rows, grenades),
            "cost": amounts(row["ResourceAmounts"]),
        }
    return out


def check(guns):
    sheet = [v for v in json.loads((DATA / "Targets.json").read_text(encoding="utf-8")).values() if v["ObjectType"] == "Emplacements"]
    want = sorted((float(v["Health"]), float(v["Repair Cost"])) for v in sheet)
    got = sorted(x for g in guns.values() for x in ((g["health"], g["repairCost"]), (g["health"] * g["emplaced"]["healthMultiplier"], g["repairCost"])))
    print(f"{len(guns)} guns -> {len(got)} rows; sheet has {len(sheet)}")
    print("  (health, repair) pairs only in sheet:", [w for w in want if w not in got])
    print("  only generated:", [g for g in got if g not in want])
    print("  null armour type:", [c for c, g in guns.items() if not g["armourType"]])


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    guns = build(*args)
    check(guns)
    if "--write" in sys.argv:
        (DATA / "emplacements.json").write_text(json.dumps(guns, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written")


if __name__ == "__main__":
    main()
