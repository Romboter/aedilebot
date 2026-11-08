"""Generate data/bunker_pieces.json (Bunker_piece.json equivalent, typed numbers) from the game export.

  gen_bunker_pieces.py STATS_DIR            # diff against data/Bunker_piece.json
  gen_bunker_pieces.py STATS_DIR --write
Each bunker piece key is the bot's modifier vocabulary (core, piece, ramp, med, rg, atg, hg, ...); which structure rows
make up its three tiers is a hand table, data/overlay/bunker_pieces.json (null = no such tier, emitted as 0 like the sheet).
Values: BPStructureDynamicData MaxHealth, StructuralIntegrity, RepairCost.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_structures import table  # noqa: E402
from resolve_vehicle_weapons import ROOT  # noqa: E402

DATA = ROOT / "data"


def build(stats):
    rows = table(stats, "BPStructureDynamicData")
    layout = json.loads((DATA / "overlay" / "bunker_pieces.json").read_text(encoding="utf-8"))
    out = {}
    for key, tiers in layout.items():
        pick = lambda f: [rows[t][f] if t else 0 for t in tiers]  # noqa: E731
        out[key] = {"health": pick("MaxHealth"), "si": pick("StructuralIntegrity"), "repair": pick("RepairCost")}
    return out


def check(pieces):
    sheet = json.loads((DATA / "Bunker_piece.json").read_text(encoding="utf-8"))
    print(f"{len(pieces)} pieces generated, {len(sheet)} in the sheet; only in sheet: {sorted(set(sheet) - set(pieces))}")
    diffs = [(k, f, [float(x) for x in sheet[k][f]], pieces[k][f]) for k in pieces if k in sheet for f in ("health", "si", "repair")
             if [float(x) for x in sheet[k][f]] != [float(x) for x in pieces[k][f]]]
    print("differences:", diffs or "none")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    pieces = build(args[0])
    check(pieces)
    if "--write" in sys.argv:
        (DATA / "bunker_pieces.json").write_text(json.dumps(pieces, indent=2) + "\n", encoding="utf-8")
        print("written")


if __name__ == "__main__":
    main()
