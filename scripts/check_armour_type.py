"""Read-only: does the blueprint's ArmourType reproduce the sheet's Mitigation Type?

  check_armour_type.py BP_DIR

For every Targets.json row with a Dev Name, finds BP<Dev Name> (or <Dev Name>), follows SuperStruct,
and takes the first ArmourType (child first). Prints match counts per ObjectType and every miss.
"""
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_vehicle_weapons import ROOT, Blueprints, walk  # noqa: E402
import json  # noqa: E402


def code_names(bps):
    """CodeName -> blueprint stem. A row key in the data tables is the blueprint's CodeName, not its file name."""
    out = {}
    for stem_, path in bps.files.items():
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r'^\s{6}"CodeName": "([^"]+)"', text, re.M):
            out.setdefault(m.group(1).lower(), stem_)
    return out


def armour_type(bps, dev, codes):
    for name in ("bp" + dev.lower(), dev.lower(), codes.get(dev.lower())):
        if not name:
            continue
        chain = bps.chain(name)
        if chain:
            for n in chain:
                for node in walk(bps.load(n)):
                    if "ArmourType" in node:
                        return node["ArmourType"].split("::")[-1], n
            return None, chain[0]
    return "NO BLUEPRINT", None


def main(bp_dir):
    bps = Blueprints(bp_dir)
    codes = code_names(bps)
    sheet = json.loads((ROOT / "data" / "Targets.json").read_text(encoding="utf-8"))
    tally = collections.defaultdict(collections.Counter)
    for key, t in sheet.items():
        dev = t.get("Dev Name")
        if not dev:
            tally[t["ObjectType"]]["no Dev Name"] += 1
            continue
        got, src = armour_type(bps, dev, codes)
        want = t.get("Mitigation Type") or None
        ok = got == want
        tally[t["ObjectType"]]["match" if ok else "miss"] += 1
        if not ok:
            print(f"{t['ObjectType']:20} {dev:36} sheet={want} export={got} ({src})")
    for ty, c in tally.items():
        print(ty, dict(c))


if __name__ == "__main__":
    main(sys.argv[1])
