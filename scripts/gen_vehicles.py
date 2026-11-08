"""Generate data/vehicles.json from the game export (layout: docs/superpowers/specs/2026-11-08-data-layout-redesign.md).

  gen_vehicles.py STATS_DIR BP_DIR            # summary + spot check against data/Targets.json
  gen_vehicles.py STATS_DIR BP_DIR --write

Rules are in docs/data-parity-scope.md (vehicle stat columns, vehicle weapon mapping, build types). Secondary weapon = the
next-best firing seat with a different mount. Not done yet: aircraft weapons (listed as WeaponCodeName on the aircraft blueprint, not as seats).
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_armour_type import code_names  # noqa: E402
from gen_structures import amounts, find, first, table  # noqa: E402
from resolve_vehicle_weapons import ROOT, Blueprints, walk  # noqa: E402

DATA = ROOT / "data"
GRAVITY, LAUNCH_HEIGHT = 980.0, 320.0  # ponytail: cm/s^2 from DefaultEngine.ini; launch height is a fitted constant (see scope doc), revalidate on physics changes


def throw_range(speed):
    """Max grenade range in metres: v/g * sqrt(v^2 + 2gh), the game's launch rule is native code."""
    return speed / GRAVITY * math.sqrt(speed**2 + 2 * GRAVITY * LAUNCH_HEIGHT) / 100


def firing_weapons(bps, chain, mounts, ammo_rows, grenades):
    """One entry per distinct firing mount, best first: highest ammo damage, ties to the lowest seat number.
    [0] is the main weapon, [1] the secondary. Empty if the vehicle has no firing seats."""
    firing = []
    for code, comp, seat in bps.seats(chain[0]):
        row = mounts.get(code.lower())
        if row and (row["MaxDistance"] > 0 or row["MaxAmmo"] > 0):  # loader seats have neither
            ammo = [a for a in bps.ammo(comp) if a.lower() in ammo_rows]
            best = max(ammo, key=lambda a: ammo_rows[a.lower()]["Damage"], default=None)
            firing.append((ammo_rows[best.lower()]["Damage"] if best else 0, -seat, code, best, comp, row))
    for bp in chain:  # aircraft list their guns as AmmoCodeName + WeaponCodeName nodes, not as seats
        for n in walk(bps.load(bp)):
            row = mounts.get(n.get("WeaponCodeName", "").lower())
            if row and n.get("AmmoCodeName", "").lower() in ammo_rows and (row["MaxDistance"] > 0 or row["MaxAmmo"] > 0):
                firing.append((ammo_rows[n["AmmoCodeName"].lower()]["Damage"], 0, n["WeaponCodeName"], n["AmmoCodeName"], None, row))
    firing.sort(key=lambda f: f[:2], reverse=True)
    out, seen = [], set()
    for _, _, code, ammo, comp, row in firing:
        if code.lower() in seen:
            continue
        if ammo is None and out:
            continue  # a mount with no ammo cannot damage anything; keep it only as the sole entry (crane seats)
        seen.add(code.lower())
        aim = bps.aim_start(comp) if comp else None
        reach = row["MaxReachability"] / 100
        if not reach and code.lower() in grenades:
            reach = round(throw_range(grenades[code.lower()]["MaxTossSpeed"]), 1)
        out.append({
            "weapon": f"{code}:{ammo}" if ammo else None,  # key into weapons.gen.json (gen_weapons_layout.py)
            "count": sum(1 for f in firing if f[2].lower() == code.lower()),
            "range": (aim if aim else row["MaxDistance"]) / 100,
            "reach": reach,
            "firingTime": row["FiringDuration"],
            "reload": row["ReloadDuration"],
            "magazine": row["MaxAmmo"],
        })
    return out


def main_weapon(bps, chain, mounts, ammo_rows, grenades):
    return next(iter(firing_weapons(bps, chain, mounts, ammo_rows, grenades)), None)


def build(stats, bp_dir):
    bps = Blueprints(bp_dir)
    codes = code_names(bps)
    mounts = {k.lower(): v for k, v in table(stats, "BPMountDynamicData").items()}
    ammo_rows = {k.lower(): v for k, v in table(stats, "BPAmmoDynamicData").items()}
    grenades = {k.lower(): v for k, v in table(stats, "BPGrenadeDynamicData").items()}
    # hand values the export lacks (e.g. Knave firing time, wiki-sourced); delete an entry to fall back to the export
    weapon_overlay = json.loads((DATA / "overlay" / "vehicle_main_weapon.json").read_text(encoding="utf-8"))
    out, skipped, no_weapon = {}, [], []
    for dev, r in table(stats, "BPVehicleDynamicData").items():
        chain = find(bps, codes, dev)
        if not chain:
            skipped.append(dev)
            continue
        disp = first(bps, chain, "DisplayName")
        armour = first(bps, chain, "ArmourType")
        build_type = first(bps, chain, "VehicleBuildType")
        build_type = build_type.split("::")[-1] if build_type else None
        cost, alt = amounts(r["ResourceAmounts"]), amounts(r["AltResourceAmounts"])
        if build_type == "VehicleFacility":
            cost = []  # facility-only: ResourceAmounts is a leftover (Flood Mk. I has no Factory route)
        pen_min = r["TankArmourMinPenetrationChance"] or (1 if not r["TankArmour"] else 0)
        weapons = firing_weapons(bps, chain, mounts, ammo_rows, grenades)
        weapon = weapons[0] if weapons else None
        if weapon and dev in weapon_overlay:
            weapon.update(weapon_overlay[dev])
        if weapon is None:
            no_weapon.append(dev)
        chances = [r["VehicleSubsystemDisableChances"]] + [r[f"VehicleSubsystemDisableChances[{i}]"] for i in (1, 2, 3)]
        out[dev] = {
            "name": disp["SourceString"] if isinstance(disp, dict) and disp.get("SourceString") else dev,
            "armourType": armour.split("::")[-1] if armour else None,
            "health": r["MaxHealth"],
            "armourHealth": r["TankArmour"],
            "penetration": {"min": pen_min, "max": 1 - r["MinTankArmourPercent"] if r["TankArmour"] else 1},
            "disableLevel": 0 if r["MinorDamagePercent"] > 1 else round(1 - r["MinorDamagePercent"], 6),  # 1000 is a sentinel
            "disableChance": dict(zip(("tracks", "engine", "mainGun", "secondaryGun"), chances)),
            "repairCost": r["RepairCost"],
            "slots": r["ItemHolderCapacity"],
            "buildType": build_type,
            "mainWeapon": weapon,
            "secondaryWeapon": weapons[1] if len(weapons) > 1 else None,
            "cost": cost,
            **({"altCost": alt} if alt and alt != cost else {}),
        }
    return out, skipped, no_weapon


def check(vehicles):
    """Spot check against the hand sheet; differences are sheet errors, not necessarily bugs."""
    sheet = {v["Dev Name"]: v for v in json.loads((DATA / "Targets.json").read_text(encoding="utf-8")).values()
             if v["ObjectType"] == "Vehicles" and v.get("Dev Name")}
    both = [d for d in sheet if d in vehicles]
    num = lambda x: float(x) if x not in (None, "") else 0.0  # noqa: E731
    fields = {
        "Health": lambda v: v["health"], "Armour Health": lambda v: v["armourHealth"], "Repair Cost": lambda v: v["repairCost"],
        "Disable Level": lambda v: v["disableLevel"], "Slots": lambda v: v["slots"],
        "Min Base Penetration Chance": lambda v: v["penetration"]["min"], "Max Base Penetration Chance": lambda v: v["penetration"]["max"],
        "Tracks Disable Chance": lambda v: v["disableChance"]["tracks"], "Engine Disable Chance": lambda v: v["disableChance"]["engine"],
        "Main Gun Disable Chance": lambda v: v["disableChance"]["mainGun"], "Secondary Gun Disable Chance": lambda v: v["disableChance"]["secondaryGun"],
    }
    print(f"{len(both)} sheet vehicles joined")
    for f, g in fields.items():
        ok = sum(1 for d in both if abs(num(sheet[d].get(f)) - g(vehicles[d])) < 1e-5)
        print(f"  {f}: {ok}/{len(both)}")
    print("  Mitigation Type:", sum(1 for d in both if sheet[d]["Mitigation Type"] == vehicles[d]["armourType"]), f"/{len(both)}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    vehicles, skipped, no_weapon = build(*args)
    print(f"{len(vehicles)} vehicles, {len(skipped)} rows skipped (no blueprint), {len(no_weapon)} without a firing seat")
    check(vehicles)
    if "--write" in sys.argv:
        (DATA / "vehicles.json").write_text(json.dumps(vehicles, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written")


if __name__ == "__main__":
    main()
