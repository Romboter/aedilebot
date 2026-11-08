"""Read-only: resolve each vehicle's weapons from the game export and diff the sheet's text columns.

vehicle blueprint -> seat (MountCodeName, MountComponent) -> BPMountDynamicData row (range, reload)
                                                          -> component ammo list -> BPAmmoDynamicData damage

  resolve_vehicle_weapons.py STATS_DIR [BP_DIR] [--report=PATH.md]   # BP_DIR defaults to STATS_DIR
  STATS_DIR/War/Content/Blueprints/Data/{BPMountDynamicData,BPAmmoDynamicData}.json
  BP_DIR/War/Content/Blueprints/**/*.json

Main weapon = the enabled seat that fires (MaxDistance > 0 or MaxAmmo > 0) with the highest ammo damage;
ties go to the lowest seat number (Silverhand Mk. IV: 40mm turret = seat 1, 68mm hull gun = seat 2).
Effective range = AimOffsetStartRange if the component has one, else MaxDistance; max range = MaxReachability.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = "Main Weapon (damage bonus)(max range, reach)(artillery range)"
RELOAD = "Reload time (pre-reload+reload) (magazine size) (artillery spread?)"


def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def stem(ref):
    return ref["ObjectPath"].rsplit("/", 1)[-1].split(".")[0]


class Blueprints:
    def __init__(self, bp_dir):
        self.files = {}
        for p in (Path(bp_dir) / "War/Content/Blueprints").rglob("*.json"):
            self.files.setdefault(p.stem.lower(), p)  # Dev Names differ in case from file names (HalfTrackMultiW)
        self.cache = {}

    def load(self, name):
        name = name.lower()
        if name not in self.files:
            return None
        if name not in self.cache:
            self.cache[name] = json.loads(self.files[name].read_text(encoding="utf-8"))
        return self.cache[name]

    def chain(self, name):
        """The blueprint and its SuperStruct parents, child first."""
        seen = []
        while name and name not in seen and self.load(name) is not None:
            seen.append(name)
            parent = next((n["SuperStruct"] for n in walk(self.load(name)) if "SuperStruct" in n), None)
            name = stem(parent) if parent else None
        return seen

    def seats(self, name):
        """(MountCodeName, component blueprint, seat number) per enabled seat. A seat is one named object; a child
        blueprint's properties override the same-named seat in its parents (Pelekys replaces the base tank's gunner)."""
        seats = {}
        for bp in reversed(self.chain(name)):
            for n in walk(self.load(bp)):
                p = n.get("Properties")
                if n.get("Name", "").endswith("_GEN_VARIABLE") and isinstance(p, dict) and any(k in p for k in ("MountCodeName", "MountComponent", "bIsEnabled")):
                    seats.setdefault(n["Name"], {}).update(p)
        out = []
        for seat, p in seats.items():
            if "MountCodeName" in p and "MountComponent" in p and p.get("bIsEnabled", True):
                number = re.search(r"Seat(\d+)", seat)
                out.append((p["MountCodeName"], stem(p["MountComponent"]), int(number.group(1)) if number else 99))
        return out

    def ammo(self, component):
        """Ammo dev names from the nearest component in the chain: MultiAmmo list, else single AmmoName."""
        for bp in self.chain(component):
            for n in walk(self.load(bp)):
                if n.get("MultiAmmo", {}).get("CompatibleAmmoNames"):
                    return n["MultiAmmo"]["CompatibleAmmoNames"]
                if isinstance(n.get("AmmoName"), str):
                    return [n["AmmoName"]]
        return []

    def aim_start(self, component):
        """AimOffsetStartRange (cm) from the nearest component in the chain, else None."""
        for bp in self.chain(component):
            for n in walk(self.load(bp)):
                if isinstance(n.get("Properties"), dict) and "AimOffsetStartRange" in n["Properties"]:
                    return n["Properties"]["AimOffsetStartRange"]
        return None


def sheet_range(text):
    """Metres from the last "(...m...)" group: [effective] or [effective, max]. None for min-max or missing forms."""
    groups = re.findall(r"\(([^()]*\d\s*m[^()]*)\)", text)
    if not groups or "-" in groups[-1]:
        return None
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", groups[-1])][:2]


def rows(stats, table):
    return json.loads((Path(stats) / "War/Content/Blueprints/Data" / f"{table}.json").read_text(encoding="utf-8"))[0]["Rows"]


def label(ammo, names):
    """Weapons.json names for the ammo dev names (the first name per ammo is the generic one)."""
    return ", ".join(dict.fromkeys(names[x.lower()][0] for x in ammo if x.lower() in names)) or "-"


def describe(code, ammo, row, names):
    rng = f"{row['Effective']:g}m / {row['MaxReachability'] / 100:g}m" if row["MaxDistance"] > 0 else "no range"
    return f"{label(ammo, names)} (`{code}`) {rng}, {row['FiringDuration']:g}+{row['ReloadDuration']:g}s, mag {row['MaxAmmo']}"


def main(stats, bp_dir, report=None):
    mounts = {k.lower(): v for k, v in rows(stats, "BPMountDynamicData").items()}  # seat code names differ in case (HalftrackMultiWGunner)
    ammo_rows = {k.lower(): v for k, v in rows(stats, "BPAmmoDynamicData").items()}  # RPGAmmo vs RpgAmmo
    targets = json.loads((ROOT / "data" / "Targets.json").read_text(encoding="utf-8"))
    weapons = json.loads((ROOT / "data" / "Weapons.json").read_text(encoding="utf-8"))
    names = {}
    for name, w in weapons.items():
        names.setdefault(w["Dev Name"].lower(), []).append(name)
    bps = Blueprints(bp_dir)

    totals = dict(vehicles=0, no_main=0, range_diff=0, reload_diff=0, ok=0)
    lines = []
    for t in targets.values():
        if t.get("ObjectType") != "Vehicles" or not (t.get(MAIN) or t.get(RELOAD)):
            continue
        totals["vehicles"] += 1
        dev = t["Dev Name"]
        firing = []
        for code, comp, seat in bps.seats("BP" + dev):
            row = mounts.get(code.lower())
            if row and (row["MaxDistance"] > 0 or row["MaxAmmo"] > 0):  # loader seats (Lordscar engineer) have neither
                ammo = bps.ammo(comp)
                damage = max([ammo_rows[a.lower()]["Damage"] for a in ammo if a.lower() in ammo_rows] or [0])
                aim = bps.aim_start(comp)
                firing.append((damage, -seat, code, ammo, dict(row, Effective=(aim if aim else row["MaxDistance"]) / 100)))
        sheet = f"{t.get(MAIN, '')} / {t.get(RELOAD, '')} / {t.get('Secondary Weapon', '')}".replace("|", "/")
        if not firing:
            totals["no_main"] += 1
            print(f"{t['Name']} [{dev}]: no firing mount found")
            lines.append((0, f"| {t['Name']} (`{dev}`) | no firing mount found | - | {sheet} | check |"))
            continue
        firing.sort(key=lambda f: f[:2], reverse=True)
        _, _, code, ammo, row = firing[0]
        problems = []
        want = [row["Effective"], row["MaxReachability"] / 100]
        got = sheet_range(t.get(MAIN, ""))
        if got and any(abs(g - w) > 0.01 for g, w in zip(got, want)):
            problems.append(f"range sheet {t[MAIN]!r} vs effective {want[0]:g}m, max {want[1]:g}m")
            totals["range_diff"] += 1
        total = row["FiringDuration"] + row["ReloadDuration"]
        first = re.match(r"\s*(\d+(?:\.\d+)?)\s*s", t.get(RELOAD, ""))
        if first and abs(float(first.group(1)) - total) > 0.01:
            problems.append(f"reload sheet {t[RELOAD]!r} vs {total:g}s ({row['FiringDuration']:g}+{row['ReloadDuration']:g})")
            totals["reload_diff"] += 1
        if problems:
            print(f"{t['Name']} [{dev}] main={code} ammo={ammo}: " + "; ".join(problems))
        else:
            totals["ok"] += 1
        others = "<br>".join(describe(c, a, r, names) for _, _, c, a, r in firing[1:]) or "-"
        result = "; ".join(problems).replace("|", "/") or "agrees"
        lines.append((1 if problems else 2, f"| {t['Name']} (`{dev}`) | {describe(code, ammo, row, names)} | {others} | {sheet} | {result} |"))
    print(totals)
    if report:
        head = (
            "# Vehicle weapons: generated from the export vs the sheet\n\n"
            f"Generated by `scripts/resolve_vehicle_weapons.py`. {totals['vehicles']} vehicles with sheet weapon text: "
            f"{totals['ok']} agree, {totals['range_diff']} range differences, {totals['reload_diff']} reload differences, "
            f"{totals['no_main']} with no firing mount.\n\n"
            "Main weapon = enabled firing seat with the highest ammo damage (ties: lowest seat number). "
            "Range is effective / max in metres; time is firing + reload in seconds. "
            "Sheet column is main weapon / reload / secondary.\n\n"
            "| Vehicle | Generated main weapon | Other firing mounts | Sheet | Result |\n| --- | --- | --- | --- | --- |\n"
        )
        Path(report).write_text(head + "\n".join(l for _, l in sorted(lines, key=lambda x: x[0])) + "\n", encoding="utf-8")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--report=")]
    out = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--report=")), None)
    main(args[0], args[1] if len(args) > 1 else args[0], out)
