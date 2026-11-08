"""Read-only: which BPVehicleDynamicData column reproduces each Targets.json vehicle column?

  check_vehicle_columns.py STATS_DIR

For every sheet column, prints the export columns that match the most rows (joined on Dev Name).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLS = [
    "Health", "Armour Health", "Min Base Penetration Chance", "Max Base Penetration Chance",
    "Tracks Disable Chance", "Engine Disable Chance", "Main Gun Disable Chance", "Secondary Gun Disable Chance",
]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main(stats):
    p = Path(stats) / "War/Content/Blueprints/Data/BPVehicleDynamicData.json"
    export = json.loads(p.read_text(encoding="utf-8"))[0]["Rows"]
    sheet = json.loads((ROOT / "data" / "Targets.json").read_text(encoding="utf-8"))
    joined = [(t, export[t["Dev Name"]]) for t in sheet.values() if t.get("ObjectType") == "Vehicles" and t.get("Dev Name") in export]
    print(f"{len(joined)} sheet vehicles joined to the export")
    for col in COLS:
        pairs = [(num(t.get(col)) or 0.0, row) for t, row in joined if col in t]
        hits = {}
        for want, row in pairs:
            for k, v in row.items():
                if num(v) is not None and abs(num(v) - want) < 1e-6:
                    hits[k] = hits.get(k, 0) + 1
        best = sorted(hits.items(), key=lambda kv: -kv[1])[:3]
        print(f"{col}: {len(pairs)} rows; " + ", ".join(f"{k} {n}/{len(pairs)}" for k, n in best))


if __name__ == "__main__":
    main(sys.argv[1])
