"""Generate data/damage.gen.json (damage type -> mitigation type -> multiplier) from DTDamageProfiles.

  gen_damage.py STATS_DIR            # diff against data/Damage.json
  gen_damage.py STATS_DIR --write
Typed numbers, no sheet-only columns ("-", "Nomitigation": the bot handles those). The name is damage.gen.json because
damage.json is the same file as the sheet's Damage.json on case-insensitive filesystems; rename when the sheet is retired.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_structures import table  # noqa: E402
from resolve_vehicle_weapons import ROOT  # noqa: E402

DATA = ROOT / "data"


def check(profiles):
    sheet = json.loads((DATA / "Damage.json").read_text(encoding="utf-8"))
    print(f"{len(profiles)} damage types generated, {len(sheet)} in the sheet; only in sheet: {sorted(set(sheet) - set(profiles))}; only generated: {sorted(set(profiles) - set(sheet))}")
    diffs = []
    extra = set()
    for t, row in profiles.items():
        s = sheet.get(t)
        if s is None:
            continue
        for m, v in row.items():
            if m not in s:
                extra.add(m)
            elif abs(float(s[m]) - v) > 1e-9:
                diffs.append((t, m, s[m], v))
        for m in s:
            if m not in row and m not in ("Name", "ObjectType", "-", "Nomitigation"):
                diffs.append((t, m, s[m], "missing"))
    print("value differences:", diffs or "none")
    print("mitigation types only in the export:", sorted(extra))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    profiles = table(args[0], "DTDamageProfiles")
    check(profiles)
    if "--write" in sys.argv:
        (DATA / "damage.gen.json").write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")
        print("written")


if __name__ == "__main__":
    main()
