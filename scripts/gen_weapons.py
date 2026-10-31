"""Regenerate Weapons.json "Damage" from the game export.

sheet damage = ammo Damage x kinetic factor x firing weapon/mount DamageMultiplier
The weapon->multiplier choice is not in the assets, so it lives in
data_manual/weapon_multipliers.json ({weapon name: "Weapon:<row>" | "Mount:<row>"}).

  gen_weapons.py STATS_DIR --seed    # (re)build the overlay from the current sheet
  gen_weapons.py STATS_DIR           # diff generated vs data/Weapons.json
  gen_weapons.py STATS_DIR --write   # apply
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "data" / "Weapons.json"
OVERLAY = ROOT / "data_manual" / "weapon_multipliers.json"
KINETIC = 1.25  # ponytail: in no exported table; applies to *Kinetic damage types + AircraftAmmo


def rows(stats, name):
    p = Path(stats) / "War/Content/Blueprints/Data" / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8"))[0]["Rows"]


def load(stats):
    mult = {}
    for kind, table in (("Weapon", "BPWeaponDynamicData"), ("Mount", "BPMountDynamicData")):
        for k, v in rows(stats, table).items():
            mult[f"{kind}:{k}"] = v["DamageMultiplier"]
    return rows(stats, "BPAmmoDynamicData"), mult


def kinetic_factor(dev, ammo):
    return KINETIC if "Kinetic" in ammo["DamageType"]["ObjectName"] or dev == "AircraftAmmo" else 1.0


def damage(w, ammo, mult, overlay, name):
    a = ammo.get(w["Dev Name"])
    if not a or not a["Damage"]:
        return None  # no ammo row (garrison/AI shells): hand-entered
    return a["Damage"] * kinetic_factor(w["Dev Name"], a) * mult[overlay[name]] if name in overlay else a["Damage"] * kinetic_factor(w["Dev Name"], a)


def seed(sheet, ammo, mult):
    overlay = {}
    for n, w in sheet.items():
        a = ammo.get(w["Dev Name"])
        if not a or not a["Damage"]:
            continue
        base = a["Damage"] * kinetic_factor(w["Dev Name"], a)
        want = float(w["Damage"])
        if abs(want - base) < 1e-6 * base:
            continue
        # ponytail: equal-valued rows tie; the first is kept, any is numerically identical
        best = min(mult, key=lambda k: abs(base * mult[k] - want))
        exact = abs(base * mult[best] - want) < 1e-4 * want
        if abs(base * mult[best] - want) > 0.02 * want:
            print(f"NO MATCH {n}: sheet {want} vs base {base}")
            continue
        overlay[n] = best
        if not exact:
            print(f"APPROX {n}: sheet {want} -> {base * mult[best]:g} via {best} (sheet typo?)")
    return overlay


def fmt(x, old):
    return old if abs(float(old) - x) < 1e-6 * max(x, 1) else repr(round(x, 4))


def main():
    stats, flags = sys.argv[1], sys.argv[2:]
    sheet = json.loads(SHEET.read_text(encoding="utf-8"))
    ammo, mult = load(stats)
    if "--seed" in flags:
        OVERLAY.write_text(json.dumps(seed(sheet, ammo, mult), indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    changed = 0
    for n, w in sheet.items():
        d = damage(w, ammo, mult, overlay, n)
        if d is None:
            continue
        new = fmt(d, w["Damage"])
        if new != w["Damage"]:
            print(f"{n}: {w['Damage']} -> {new}")
            w["Damage"] = new
            changed += 1
    print(f"{changed} changed of {len(sheet)}")
    if "--write" in flags:
        SHEET.write_text(json.dumps(sheet, indent=4) + "\n", encoding="utf-8")
    elif changed:
        sys.exit(1)  # drift: sheet differs from the export


if __name__ == "__main__":
    main()
