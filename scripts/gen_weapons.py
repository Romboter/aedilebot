"""Regenerate Weapons.json damage values from a game's extracted DataTables.

Sheet damage = ammo Damage × kinetic factor × firing weapon/mount multiplier.

IMPORTANT: data_manual/weapon_multipliers.json is a manually reviewed
numeric-multiplier lookup, NOT verified physical weapon-to-mount identity.
In particular, --seed chooses numerically matching rows and is exploratory.
Never automatically regenerate the overlay or publish --write output without
reviewing the data diff against a pinned game build.

  python scripts/gen_weapons.py STATS_DIR           # check for drift (read-only)
  python scripts/gen_weapons.py STATS_DIR --write   # apply reviewed changes
  python scripts/gen_weapons.py STATS_DIR --seed    # reseed guessed mapping (manual only)
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "data" / "Weapons.json"
OVERLAY = ROOT / "data_manual" / "weapon_multipliers.json"
KINETIC = 1.25  # Observed rule, not present in exported DataTables.
VARIANT_LABEL = re.compile(r"\(([+-]\d+)% (?:HV|LV)\)")


def rows(stats: Path, name: str) -> dict:
    p = Path(stats) / "War/Content/Blueprints/Data" / f"{name}.json"
    value = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value or not isinstance(value[0].get("Rows"), dict):
        raise ValueError(f"Missing/invalid Rows dictionary in {p}")
    return value[0]["Rows"]


def load(stats: Path) -> tuple[dict, dict]:
    mult = {}
    for kind, table in (("Weapon", "BPWeaponDynamicData"), ("Mount", "BPMountDynamicData")):
        for k, v in rows(stats, table).items():
            mult[f"{kind}:{k}"] = v["DamageMultiplier"]
    return rows(stats, "BPAmmoDynamicData"), mult


def finite_number(value: object, description: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{description} is not numeric: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"{description} is not finite: {value!r}")
    return result


def kinetic_factor(dev: str, ammo: dict) -> float:
    return KINETIC if "Kinetic" in ammo["DamageType"]["ObjectName"] or dev == "AircraftAmmo" else 1.0


def damage(w: dict, ammo: dict, mult: dict, overlay: dict, name: str) -> float | None:
    a = ammo.get(w["Dev Name"])
    if not a or a.get("Damage") is None:
        return None  # No ammo row: hand-entered, not generated.
    amount = finite_number(a["Damage"], f"ammo damage for {name}")
    if amount < 0:
        raise ValueError(f"Negative ammo damage for {name}")

    multiplier = 1.0
    if name in overlay:
        reference = overlay[name]
        if reference not in mult:
            raise ValueError(f"Unresolved multiplier for {name}: {reference!r}")
        multiplier = finite_number(mult[reference], f"multiplier for {name} ({reference})")
        if multiplier <= 0:
            raise ValueError(f"Nonpositive multiplier for {name}: {multiplier}")
    elif VARIANT_LABEL.search(name):
        # An annotated HV/LV variant is known to require a non-default factor.
        raise ValueError(f"Missing multiplier mapping for explicitly labeled variant: {name}")

    label = VARIANT_LABEL.search(name)
    if label:
        expected = 1.0 + int(label.group(1)) / 100.0
        # Foxhole convention labels -33% LV as 0.66, not precisely 0.67.
        if not math.isclose(multiplier, expected, rel_tol=0.0, abs_tol=0.011):
            raise ValueError(
                f"Multiplier for {name} is {multiplier:g}, inconsistent with "
                f"its {label.group(0)} annotation (expected about {expected:g}). "
                "Review this curated mapping before updating game data."
            )

    result = amount * kinetic_factor(w["Dev Name"], a) * multiplier
    if not math.isfinite(result):
        raise ValueError(f"Computed non-finite damage for {name}")
    return result


def seed(sheet: dict, ammo: dict, mult: dict) -> dict:
    """Exploratory numeric match only; matching values do not prove identity."""
    overlay = {}
    if not mult:
        raise ValueError("Cannot seed: game export contains no weapon/mount multipliers")
    for n, w in sheet.items():
        a = ammo.get(w["Dev Name"])
        if not a or a.get("Damage") is None:
            continue
        base = finite_number(a["Damage"], f"ammo damage for {n}") * kinetic_factor(w["Dev Name"], a)
        want = finite_number(w["Damage"], f"current sheet damage for {n}")
        if math.isclose(want, base, rel_tol=1e-6, abs_tol=0):
            continue
        # Numeric coincidences are not proof of the real weapon/mount identity.
        best = min(mult, key=lambda k: abs(base * finite_number(mult[k], f"multiplier {k}") - want))
        actual = base * finite_number(mult[best], f"multiplier {best}")
        if abs(actual - want) > 0.02 * max(abs(want), 1e-9):
            print(f"NO MATCH {n}: sheet {want:g} vs base {base:g}")
            continue
        overlay[n] = best
        if not math.isclose(actual, want, rel_tol=1e-4, abs_tol=0):
            print(f"APPROX {n}: sheet {want:g} -> {actual:g} via {best} (manual review required)")
    return overlay


def fmt(x: float, old: object) -> object:
    previous = finite_number(old, "previous sheet damage")
    if math.isclose(previous, x, rel_tol=1e-6, abs_tol=0):
        return old
    return repr(round(x, 4))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stats_dir", type=Path, help="Directory containing War/Content/Blueprints/Data JSON")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Update data/Weapons.json after review")
    mode.add_argument("--seed", action="store_true", help="Regenerate guessed multiplier mapping; manual review only")
    args = parser.parse_args(argv)

    sheet = json.loads(SHEET.read_text(encoding="utf-8"))
    ammo, mult = load(args.stats_dir)

    if args.seed:
        print("WARNING: --seed infers numeric coincidences, not weapon/mount identity. Review every mapping.")
        candidate = seed(sheet, ammo, mult)
        if candidate != json.loads(OVERLAY.read_text(encoding="utf-8")):
            OVERLAY.write_text(json.dumps(candidate, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0

    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    stale = sorted(set(overlay) - set(sheet))
    if stale:
        raise ValueError(f"Multiplier mapping references unknown weapon(s): {', '.join(stale)}")
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
    if args.write and changed:
        SHEET.write_text(json.dumps(sheet, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    elif changed:
        return 1  # Dry-run drift detected; do not touch the source.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
