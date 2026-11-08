"""Generate data/locations.gen.csv (hex, location name, type) from the game's placed town and relic actors.

  gen_locations.py ACTORS_JSON STATIC_DIR            # summary + diff against data/Locations.csv
  gen_locations.py ACTORS_JSON STATIC_DIR --write
ACTORS_JSON: per-hex actors {"AcrithiaHex": [{"kind", "x", "y"}]} from the extractor spike (placed actors in each hex's .umap;
kind: TownBase1/2/3 = Post Office / School / Town Center, RelicBase1/2/3 = Small / Medium / Large Relic).
STATIC_DIR: War API /worldconquest/maps/<Hex>/static JSON per hex; the location name is the nearest mapTextItems marker
(world -> API: x = 0.5 + wx/218400, y = 0.5 + wy/189000). Matches farther than WEAK are reported, not dropped.
The bot reads only (name -> type); "TH" labels in the old sheet are the same types, so types are emitted canonical.
Duplicate actors at identical coordinates collapse to one. Not generated: Marban Hollow if the actors file lacks it.
"""
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
WEAK = 0.05  # correct matches reach 0.02-0.06 (markers sit beside the actor); distance alone is a poor cutoff, review the diff instead


def key(s):
    return re.sub(r"[^a-z]", "", re.sub(r"^the|hex$", "", s.lower().strip()))


def build(actors, static_dir):
    rows, weak = [], []
    for hexname, found in sorted(actors.items()):
        api = Path(static_dir) / f"{hexname}.json"
        if not api.exists():
            api = next((p for p in Path(static_dir).glob("*.json") if key(p.stem) == key(hexname)), None)
        if api is None:
            print("no static data for", hexname)
            continue
        marks = json.loads(api.read_text(encoding="utf-8"))["mapTextItems"]
        uniq = {(a["x"], a["y"], a["kind"]): a for a in found}.values()  # duplicate actors at identical coordinates collapse
        pairs = sorted((((0.5 + a["x"] / 218400 - m["x"]) ** 2 + (0.5 + a["y"] / 189000 - m["y"]) ** 2) ** 0.5, i, j)
                       for i, a in enumerate(uniq) for j, m in enumerate(marks))
        uniq = list(uniq)
        used_a, used_m = set(), set()
        for d, i, j in pairs:  # greedy one-to-one: two actors never take the same marker (nearest-only did)
            if i in used_a or j in used_m:
                continue
            used_a.add(i)
            used_m.add(j)
            rows.append((hexname, fold(marks[j]["text"]), uniq[i]["kind"]))
            if d > WEAK:
                weak.append((hexname, fold(marks[j]["text"]), uniq[i]["kind"], round(d, 4)))
    return rows, weak


def fold(s):
    """API marker text has accents (Scath Passing, Sidhe Fall); the sheet and what players type are ASCII."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def canon(t):
    return re.sub(r" TH$", "", t.strip())


def check(rows, weak):
    old = list(csv.reader(open(ROOT / "data" / "Locations.csv", encoding="utf-8-sig")))
    by_hex = {key(r[0]): set() for r in old}
    for h, n, t in old:
        by_hex[key(h)].add((n.strip().lower(), canon(t)))
    new = {}
    for h, n, t in rows:
        new.setdefault(key(h), set()).add((n.strip().lower(), t))
    # hex display names that differ from the API ids (the sheet's THE MOORS = MooringCountyHex etc.)
    print(f"{len(rows)} locations in {len(new)} hexes; old sheet {len(old)} rows in {len(by_hex)} hexes")
    print("hexes only in the old sheet (no key match):", sorted(set(by_hex) - set(new)))
    print("hexes only generated:", sorted(set(new) - set(by_hex)))
    same = [h for h in new if h in by_hex and new[h] == by_hex[h]]
    print(f"{len(same)} of {len(set(new) & set(by_hex))} comparable hexes identical")
    for h in sorted(set(new) & set(by_hex) - set(same)):
        print(f"  {h}: only old {sorted(by_hex[h] - new[h])}; only new {sorted(new[h] - by_hex[h])}")
    print("weak matches (distance > %s):" % WEAK, weak)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    rows, weak = build(json.loads(Path(args[0]).read_text(encoding="utf-8")), args[1])
    check(rows, weak)
    if "--write" in sys.argv:
        with open(ROOT / "data" / "locations.gen.csv", "w", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\n").writerows(rows)
        print("written")


if __name__ == "__main__":
    main()
