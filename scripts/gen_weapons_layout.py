"""Generate data/weapons.gen.json from the game export (layout: docs/superpowers/specs/2026-11-08-data-layout-redesign.md).

The weapon list comes from the game, not the sheet:
  infantry: ItemPickups blueprint (CodeName, DisplayName, ItemComponentClass) -> component CompatibleAmmoCodeName,
            multiplier from BPWeaponDynamicData[CodeName]
  mounted:  every enabled vehicle seat (MountCodeName + component ammo list), multiplier from BPMountDynamicData
damage = ammo Damage x 1.25 (kinetic types and AircraftAmmo) x multiplier; damageType and shelterBonus from the ammo's
damage type class. Keys: infantry CodeName, or "<MountCodeName>:<AmmoCode>". Hand values live in data/overlay/.

  gen_weapons_layout.py STATS_DIR BP_DIR            # summary + coverage of the sheet's 107 rows
  gen_weapons_layout.py STATS_DIR BP_DIR --write   # data/weapons.gen.json
Not done yet: emplacement, tripod and aircraft weapons (separate blueprint paths), garrison/AI shells with no ammo row.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_weapons import KINETIC, damage_types  # noqa: E402
from gen_structures import table  # noqa: E402
from resolve_vehicle_weapons import ROOT, Blueprints, stem, walk  # noqa: E402

DATA = ROOT / "data"


def display(props):
    d = props.get("DisplayName")
    return d.get("SourceString") if isinstance(d, dict) else None


def cdo(bps, name):
    return next((o["Properties"] for o in bps.load(name) if o["Name"].startswith("Default__") and o.get("Properties")), {})


def infantry_ammo(bps, component):
    for c in bps.chain(component):
        for n in walk(bps.load(c)):
            p = n.get("Properties")
            if isinstance(p, dict) and "CompatibleAmmoCodeName" in p:
                return p["CompatibleAmmoCodeName"]
    return None


def build(stats, bp_dir):
    bps = Blueprints(bp_dir)
    ammo_rows = {k.lower(): (k, v) for k, v in table(stats, "BPAmmoDynamicData").items()}
    weapon_rows = {k.lower(): v for k, v in table(stats, "BPWeaponDynamicData").items()}
    mount_rows = {k.lower(): v for k, v in table(stats, "BPMountDynamicData").items()}
    dt = damage_types(bp_dir)
    out, no_ammo = {}, []

    def add(key, name, ammo, mult, source, user=None):
        hit = ammo_rows.get(ammo.lower())
        if not hit or not hit[1]["Damage"]:
            no_ammo.append(key)
            return
        code, a = hit
        factor = KINETIC if "Kinetic" in a["DamageType"]["ObjectName"] or code == "AircraftAmmo" else 1.0
        cls = a["DamageType"]["ObjectName"].split("'")[1].removesuffix("_C")
        dtype, shelter = dt.get(cls, (None, False))
        w = out.setdefault(key, {"name": name, "ammo": code, "damage": round(a["Damage"] * factor * mult, 4),
                                 "damageType": dtype, "shelterBonus": shelter, "source": source})
        if user:
            w.setdefault("users", []).append(user)

    for f in bps.files.values():
        if f.parent.name != "ItemPickups":
            continue
        p = cdo(bps, f.stem)
        if p.get("ItemComponentClass") and p.get("CodeName"):
            ammo = infantry_ammo(bps, stem(p["ItemComponentClass"]))
            if ammo:
                add(p["CodeName"], display(p), ammo, (weapon_rows.get(p["CodeName"].lower()) or {}).get("DamageMultiplier", 1), "infantry")

    for f in bps.files.values():
        if f.parent.name == "ItemPickups" or not {"Vehicles", "Structures"} & set(f.parts):
            continue
        for n in walk(bps.load(f.stem)):  # aircraft list their guns as AmmoCodeName + WeaponCodeName, not as seats
            if "AmmoCodeName" in n and "WeaponCodeName" in n and n["WeaponCodeName"].lower() in mount_rows:
                add(f"{n['WeaponCodeName']}:{n['AmmoCodeName']}", display(cdo(bps, f.stem)) or f.stem,
                    n["AmmoCodeName"], mount_rows[n["WeaponCodeName"].lower()]["DamageMultiplier"], "mount", f.stem)
        for code, comp, _seat in bps.seats(f.stem):
            row = mount_rows.get(code.lower())
            if not row or not (row["MaxDistance"] > 0 or row["MaxAmmo"] > 0):
                continue
            veh = display(cdo(bps, f.stem)) or f.stem
            for a in bps.ammo(comp):
                add(f"{code}:{a}", veh, a, row["DamageMultiplier"], "mount", f.stem)
    # AI weapons (pillboxes, ATGs, coastal and AA guns, ship turrets): damage sits on the structure blueprint, no ammo row.
    # DamageAttributes is the primary (infantry) damage, DamageAttributesAlternate the damage against everything else
    # (wiki, Rifle Garrison: 45 vs infantry, 50 vs the rest). A block without DamageType gets no kinetic factor.
    for stem_, f in bps.files.items():
        if f.parent.name == "ItemPickups":
            continue
        for n in walk(bps.load(stem_)):
            dp = n.get("DamageParams")  # artillery garrisons (Howitzer): radial HE shell, BaseAmount at the centre
            if isinstance(dp, dict) and dp.get("BaseAmount") and isinstance(dp.get("Type"), dict):
                cls = dp["Type"]["ObjectName"].split("'")[1].removesuffix("_C")
                dtype, shelter = dt.get(cls, (None, False))
                out.setdefault(f"{stem_}:DamageParams", {"name": display(cdo(bps, stem_)) or stem_, "ammo": None,
                               "damage": round(dp["BaseAmount"] * (KINETIC if "Kinetic" in cls else 1.0), 4), "damageType": dtype,
                               "shelterBonus": shelter, "source": "ai", "radius": dp["Radius"] / 100, "innerRadius": dp["InnerRadius"] / 100,
                               "falloff": dp["Falloff"]})
            da = n.get("DamageAttributes")
            if not (isinstance(da, dict) and da.get("WeaponDamage")):
                continue
            blocks = [("WeaponDamage", da, None)]
            alt = n.get("DamageAttributesAlternate")
            if isinstance(alt, dict) and alt.get("WeaponDamage"):
                blocks.append(("WeaponDamageAlternate", alt, da))
            for suffix, blk, fallback in blocks:
                t = blk.get("DamageType") or (fallback or {}).get("DamageType")
                cls = t["ObjectName"].split("'")[1].removesuffix("_C") if isinstance(t, dict) else None
                dtype, shelter = dt.get(cls, (None, False)) if cls else (None, False)
                factor = KINETIC if cls and "Kinetic" in cls else 1.0
                out.setdefault(f"{stem_}:{suffix}", {"name": display(cdo(bps, stem_)) or stem_, "ammo": None,
                               "damage": round(blk["WeaponDamage"] * factor, 4), "damageType": dtype, "shelterBonus": shelter,
                               "source": "ai" if suffix == "WeaponDamage" else "ai-nonInfantry"})
    # thrown/placed items, mines and shells: the ammo row is the weapon (multiplier 1); named by the item pickup with the same CodeName
    pickups = {cdo(bps, f.stem).get("CodeName"): display(cdo(bps, f.stem)) for f in bps.files.values() if f.parent.name == "ItemPickups"}
    for code, a in table(stats, "BPAmmoDynamicData").items():
        base = a["Damage"] * (KINETIC if "Kinetic" in a["DamageType"]["ObjectName"] or code == "AircraftAmmo" else 1.0)
        if not any(w["ammo"] == code and abs(w["damage"] - base) < 1e-6 for w in out.values()):  # nothing fires it unmodified
            add(code, pickups.get(code) or code, code, 1, "ammo")
    return dict(sorted(out.items())), no_ammo


def check(weapons):
    sheet = json.loads((DATA / "Weapons.json").read_text(encoding="utf-8"))
    pool = {}
    for k, w in weapons.items():
        pool.setdefault(w["ammo"], []).append((k, w))
    miss = []
    for n, s in sheet.items():
        try:
            want = float(s["Damage"])
        except ValueError:
            continue
        if not any(abs(w["damage"] - want) < 5e-3 * max(want, 1) for _, w in pool.get(s["Dev Name"], []) + pool.get(None, [])):  # AI weapons have no ammo row; 81.25 vs sheet 81 needs the looser tolerance
            miss.append((n, s["Dev Name"], want))
    print(f"{len(sheet) - len(miss)}/{len(sheet)} sheet rows have a generated weapon with the same ammo and damage")
    for m in miss:
        print("  no match:", *m)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    weapons, no_ammo = build(*args)
    print(f"{len(weapons)} weapons ({sum(w['source'] == 'infantry' for w in weapons.values())} infantry), {len(no_ammo)} skipped (no ammo row)")
    check(weapons)
    if "--write" in sys.argv:
        # ponytail: weapons.json would collide with the sheet Weapons.json on case-insensitive filesystems; rename when the sheet is retired
        (DATA / "weapons.gen.json").write_text(json.dumps(weapons, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written")


if __name__ == "__main__":
    main()
