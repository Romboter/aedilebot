"""Seed data/overlay/names.json: legacy sheet key -> generated entry + hand names (aliases).

  seed_names.py            # rebuild from data/Targets.json + data/Weapons.json (the legacy sheet) and the generated files
The bot's keys and "Additional Names" are hand-curated, so they live here (hand by nature); the numbers come from the
generated files. Each entry is {"from": "<file>:<key>", "aliases": "a;b"}, or {"static": <legacy row>} for rows with no
game source (Garage, Oil Well, Wood bridge, the player characters). Order is the legacy order (alias collisions depend on it).
Joins: Dev Name (via overlay/dev_name_aliases.json); emplacements and tripods by name tokens then elimination; weapons by
ammo and damage, with a small hand table for the AI shells. Unresolved rows are printed and kept as static.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
sys.stdout.reconfigure(encoding="utf-8")
AI_SHELLS = {  # legacy weapon name -> generated key (hand: nothing in the data links these)
    "M925 Austringer Man-O-War Moray Torpedo (-30% LV)": "AircraftTorpedoWDriver:AircraftTorpedoAmmo",  # the sheet pairs it with the Moray ammo: sheet error
    "Anti-Tank Rifle Pillbox Ammo": "bpatpillbox:WeaponDamage",
    "T1 ATG Shell": "bpatgunait1:WeaponDamage", "T2 ATG Shell": "bpatgunait2:WeaponDamage", "T3 ATG Shell": "bpatgunait3:WeaponDamage",
    "Rifle Garrison ammo": "bprifleait1:WeaponDamageAlternate", "Howitzer Garrison Shell": "bpartilleryait1:DamageParams",
    "Large Ship AI Shell": "bplargeshipaiartillerygunturretcomponent:WeaponDamage", "AI Anti-Air Gun Shell": "bpaagunai:WeaponDamage",
    "Coastal Gun Shell": "bpcoastalgun:WeaponDamage",
}


def load(name):
    return json.loads((D / name).read_text(encoding="utf-8"))


def toks(s):
    return set(re.findall(r"[a-z0-9]+", re.sub(r"\((un)?emplaced\)", "", s.lower())))


def assign(rows, cands, score):
    """rows: {legacy key: tokens}; cands: {new key: tokens}. Best token overlap first, then elimination."""
    out, free = {}, dict(cands)
    pending = dict(rows)
    while pending and free:
        best = max(((score(rt, ct), r, c) for r, rt in pending.items() for c, ct in free.items()), key=lambda x: x[0])
        if best[0] <= 0:
            if len(pending) == len(free):  # elimination: pair what is left in order
                for (r, _), (c, _) in zip(pending.items(), free.items()):
                    out[r] = c
            break
        out[best[1]] = best[2]
        del pending[best[1]], free[best[2]]
    return out


def main():
    targets, weapons = load("Targets.json"), load("Weapons.json")
    alias = load("overlay/dev_name_aliases.json")
    new = {f: load(f + ".json") for f in ("vehicles", "structures", "aircraft_parts", "emplacements", "tripods")}
    gen_w = load("weapons.gen.json")
    names, unresolved = {}, []

    def entry(key, src, row):
        names[key] = {"from": src, "type": row["ObjectType"], "name": row["Name"], "aliases": row.get("Additional Names", "")}

    # rows with a Dev Name
    where = {"Vehicles": ("vehicles",), "Structures": ("structures",), "Multitier_structures": ("structures",), "Aircraft_Parts": ("aircraft_parts",), "Tripods": ("tripods",)}
    todo = {"Emplacements": {}, "Tripods": {}}
    for key, row in targets.items():
        dev = row.get("Dev Name", "").strip()
        dev = alias.get(dev, dev)
        files = where.get(row["ObjectType"], ())
        if not dev:  # no Dev Name: the sheet key itself is the game key (OilTanker, SmallTrainEngine, ...)
            dev = next((k for f in files for k in new[f] if k.lower() == key.lower()), "")
        hit = next((f for f in files if dev and dev in new[f]), None)
        if hit:
            entry(key, f"{hit}:{dev}", row)
        elif row["ObjectType"] in todo:
            todo[row["ObjectType"]][key] = row
        else:
            names[key] = {"static": row}
            unresolved.append((row["ObjectType"], key))
    # emplacements: legacy rows are gun x (Unemplaced|Emplaced); the base gun is the match
    base = {}
    for key, row in todo["Emplacements"].items():
        b = re.sub(r"\s*\((Un)?emplaced\)", "", key, flags=re.I)
        base.setdefault(next((x for x in base if toks(x) == toks(b)), b), []).append(key)  # quote characters differ between the two rows
    gun = assign({b: toks(b) for b in base}, {k: toks(v["name"]) for k, v in new["emplacements"].items()}, lambda a, b: len(a & b))
    for b, keys in base.items():
        for k in keys:
            if b in gun:
                names[k] = {"from": f"emplacements:{gun[b]}", "type": "Emplacements", "name": targets[k]["Name"], "variant": "emplaced" if re.search(r"\(Emplaced\)", k, re.I) else "unemplaced", "aliases": targets[k].get("Additional Names", "")}
            else:
                names[k] = {"static": targets[k]}
                unresolved.append(("Emplacements", k))
    used = {v["from"].split(":")[1] for v in names.values() if v.get("from", "").startswith("tripods:")}
    tri = assign({k: toks(k) for k in todo["Tripods"]}, {k: toks(v["name"]) for k, v in new["tripods"].items() if k not in used}, lambda a, b: len(a & b))
    for k, row in todo["Tripods"].items():
        if k in tri:
            entry(k, f"tripods:{tri[k]}", row)
        else:
            names[k] = {"static": row}
            unresolved.append(("Tripods", k))
    # keep legacy order
    names = {k: names[k] for k in targets if k in names}
    # weapons
    wnames = {}
    for key, row in weapons.items():
        ammo, dmg = row["Dev Name"], float(row["Damage"])
        if key in AI_SHELLS:
            g = AI_SHELLS[key]
        else:
            inf, mount = row.get("Infantry Weapon Dev Name", "").strip(), row.get("Mount Dev Name", "").strip()
            cands = [k for k, w in gen_w.items() if w["ammo"] == ammo and abs(w["damage"] - dmg) < 5e-3 * max(dmg, 1)]
            pick = [k for k in cands if (inf and k == inf) or (mount and k.lower().startswith(mount.lower() + ":"))] or [k for k in cands if k == ammo] or cands
            g = pick[0] if pick else None
        if g is None:
            wnames[key] = {"static": row}
            unresolved.append(("Weapons", key))
        else:
            wnames[key] = {"from": f"weapons:{g}", "name": row["Name"], "dev": row["Dev Name"], "aliases": row.get("Additional Names", "")}
            if gen_w[g]["damageType"] is None:  # the export names no damage type (Rifle/MG garrisons): keep the sheet's (wiki: Light/Heavy Kinetic)
                wnames[key]["damageType"] = row["DamageType"]
    # caliber labels for the statsheet's weapon text: ammo code -> the sheet's plain-ammo row name ("75mm")
    labels = {row["Dev Name"]: row["Name"] for row in weapons.values() if not any(row.get(f, "").strip() for f in ("Infantry Weapon Dev Name", "Vehicle Dev Name", "Mount Dev Name", "Emplacement Dev Name", "Tripod Dev Name")) and "(" not in row["Name"]}
    (D / "overlay" / "ammo_labels.json").write_text(json.dumps(labels, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (D / "overlay" / "names.json").write_text(json.dumps({"targets": names, "weapons": wnames}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(len(names), "targets,", len(wnames), "weapons; static/unresolved:", len(unresolved))
    for u in unresolved:
        print("  ", u)


if __name__ == "__main__":
    main()
