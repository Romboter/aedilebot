"""Generate data/structures.json and data/materials.json from the game export (layout: docs/superpowers/specs/2026-11-08-data-layout-redesign.md).

  gen_structures.py STATS_DIR BP_DIR                 # summary + spot check against data/Targets.json
  gen_structures.py STATS_DIR BP_DIR --write         # write the two files
  gen_structures.py STATS_DIR BP_DIR --seed-overlay  # (re)build data/overlay/armour_types.json from the sheet

Rows come from BPStructureDynamicData; a row with no blueprint is skipped. Emplacements and tripods get their own files.
Armour type: blueprint ArmourType, else the hand overlay, else null.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_armour_type import code_names  # noqa: E402
from resolve_vehicle_weapons import ROOT, Blueprints, walk  # noqa: E402

DATA = ROOT / "data"
OVERLAY = DATA / "overlay" / "armour_types.json"
ALIASES = DATA / "overlay" / "dev_name_aliases.json"  # sheet Dev Name -> game key, where the sheet is wrong


def table(stats, name):
    p = Path(stats) / "War/Content/Blueprints/Data" / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8"))[0]["Rows"]


def find(bps, codes, dev):
    for name in ("bp" + dev.lower(), dev.lower(), codes.get(dev.lower())):
        if name and bps.chain(name):
            return bps.chain(name)
    return None


def first(bps, chain, key):
    for n in chain:
        for node in walk(bps.load(n)):
            if key in node:
                return node[key]
    return None


def amounts(a):
    out = [a["Resource"]] + a["OtherResources"]
    return [{"code": r["CodeName"], "qty": r["Quantity"]} for r in out if r["CodeName"] != "None" and r["Quantity"]]


def materials(bps, codes_used):
    """code -> display name, from each material's pickup/component blueprint."""
    out = {}
    for stem_ in bps.files:
        if "pickup" not in stem_ and "component" not in stem_:
            continue
        for n in walk(bps.load(stem_)):
            c = n.get("CodeName")
            if c in codes_used and isinstance(n.get("DisplayName"), dict):
                out.setdefault(c, n["DisplayName"]["SourceString"])
    return out


def build(stats, bp_dir):
    bps = Blueprints(bp_dir)
    codes = code_names(bps)
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8")) if OVERLAY.exists() else {}
    structs, skipped = {}, []
    for dev, r in table(stats, "BPStructureDynamicData").items():
        chain = find(bps, codes, dev)
        path = str(bps.files[chain[0]]).replace("\\", "/") if chain else ""
        if not chain or "/Emplacements/" in path or chain[0].startswith("bpdeployed"):
            skipped.append(dev)
            continue
        disp = first(bps, chain, "DisplayName")
        armour = first(bps, chain, "ArmourType")
        cost, alt = amounts(r["ResourceAmounts"]), amounts(r["AltResourceAmounts"])
        structs[dev] = {
            "name": disp["SourceString"] if isinstance(disp, dict) and disp.get("SourceString") else dev,
            "armourType": armour.split("::")[-1] if armour else overlay.get(dev),
            "health": r["MaxHealth"],
            "repairCost": r["RepairCost"],
            "decay": {"startHours": r["DecayStartHours"], "durationHours": r["DecayDurationHours"]},
            "structuralIntegrity": r["StructuralIntegrity"],
            "storedItemCapacity": r["StoredItemCapacity"],
            "ramDamageFlags": r["RamDamageReceivedFlags"],
            "harvestable": r["bCanBeHarvested"],
            "vaultable": r["IsVaultable"],
            "damagedWhenDrivenOver": r["bIsDamagedWhileDrivingOver"],
            "cost": cost,
            **({"altCost": alt} if alt and alt != cost else {}),  # ponytail: omit when identical, spec rule
        }
    used = {c["code"] for s in structs.values() for c in s["cost"] + s.get("altCost", [])}
    mats = materials(bps, used)
    missing = used - set(mats)
    assert not missing, f"no display name for {sorted(missing)}"
    return structs, dict(sorted(mats.items())), skipped


def seed_overlay(stats, bp_dir):
    """Sheet Mitigation Type for rows whose blueprint chain has no ArmourType."""
    bps = Blueprints(bp_dir)
    codes = code_names(bps)
    sheet = json.loads((DATA / "Targets.json").read_text(encoding="utf-8"))
    alias = json.loads(ALIASES.read_text(encoding="utf-8"))
    out = {}
    for v in sheet.values():
        dev = v.get("Dev Name")
        if v["ObjectType"] != "Structures" or not dev or not v.get("Mitigation Type"):
            continue
        dev = alias.get(dev, dev)
        chain = find(bps, codes, dev)
        if chain and first(bps, chain, "ArmourType") is None:
            out[dev] = v["Mitigation Type"]
    OVERLAY.parent.mkdir(exist_ok=True)
    OVERLAY.write_text(json.dumps(dict(sorted(out.items())), indent=2) + "\n", encoding="utf-8")
    print(f"{len(out)} overlay entries -> {OVERLAY}")


def check(structs):
    """Spot check against the hand sheet: counts of joined rows and field matches (differences are sheet errors)."""
    alias = json.loads(ALIASES.read_text(encoding="utf-8"))
    sheet = {alias.get(v["Dev Name"], v["Dev Name"]): v for v in json.loads((DATA / "Targets.json").read_text(encoding="utf-8")).values()
             if v["ObjectType"] == "Structures" and v.get("Dev Name")}
    print("sheet rows with no generated structure:", sorted(d for d in sheet if d not in structs))
    both = [d for d in sheet if d in structs]
    same = lambda d, f, g: float(sheet[d][f] or "nan") == g(structs[d])  # noqa: E731
    for f, g in (("Health", lambda s: s["health"]), ("RepairCost", lambda s: s["repairCost"])):
        ok = sum(1 for d in both if sheet[d].get(f) not in (None, "") and same(d, f, g))
        print(f"{f}: {ok}/{len(both)} match the sheet")
    arm = sum(1 for d in both if sheet[d]["Mitigation Type"] == structs[d]["armourType"])
    print(f"armourType: {arm}/{len(both)} match the sheet; {sum(1 for s in structs.values() if s['armourType'] is None)} null")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    if "--seed-overlay" in sys.argv:
        return seed_overlay(*args)
    structs, mats, skipped = build(*args)
    print(f"{len(structs)} structures, {len(mats)} materials, {len(skipped)} rows skipped (no blueprint, emplacement or tripod)")
    check(structs)
    if "--write" in sys.argv:
        (DATA / "structures.json").write_text(json.dumps(structs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (DATA / "materials.json").write_text(json.dumps(mats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written")


if __name__ == "__main__":
    main()
