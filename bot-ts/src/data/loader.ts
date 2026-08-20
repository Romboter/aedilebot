// Port of parse.py's data-loading functions: reads data/*.json + Locations.csv
// into typed in-memory structures. Straight, behavior-preserving port — no
// reshaping (data files stay byte-identical), per the rewrite plan.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import type {
  BunkerPieceTable,
  DamageTable,
  Entity,
  LocationRow,
  TargetEntry,
  WeaponEntry,
} from "./schema.js";

function loadJson<T>(dataDir: string, filename: string): T {
  const raw = readFileSync(path.join(dataDir, filename), "utf-8");
  return JSON.parse(raw) as T;
}

// Locations.csv has no header row, 3 plain unquoted columns (hex, location,
// type — confirmed by inspection: no field contains a comma or quote), so a
// full RFC4180 CSV parser would be pure overhead here; a per-line split
// covers the actual data. \r is stripped since the file uses CRLF line
// endings and Node doesn't split on \r\n the way Python's csv module does.
function parseLocationsCsv(raw: string): LocationRow[] {
  const rows: LocationRow[] = [];
  for (const line of raw.split("\n")) {
    const fields = line.replace(/\r$/, "").split(",");
    if (fields.length < 3) {
      continue;
    }
    rows.push({
      hexName: fields[0]!.trim(),
      locationName: fields[1]!.trim(),
      locationType: fields[2]!.trim(),
    });
  }
  return rows;
}

/** Map<locationName, locationType> — last row for a given name wins, matching
 * Python's dict[location_name] = location_type overwrite-on-duplicate. */
export function loadLocationsFromCsv(dataDir: string): Map<string, string> {
  const raw = readFileSync(path.join(dataDir, "Locations.csv"), "utf-8");
  const locations = new Map<string, string>();
  for (const row of parseLocationsCsv(raw)) {
    locations.set(row.locationName, row.locationType);
  }
  return locations;
}

const LOCATION_TYPE_TO_TARGET_KEY: Record<string, string> = {
  "Post Office TH": "Town Base (Post Office)",
  "Post Office": "Town Base (Post Office)",
  "Town Center TH": "Town Base (Town Centre)",
  "Town Center": "Town Base (Town Centre)",
  "School TH": "Town Base (School)",
  School: "Town Base (School)",
  "Small Relic": "Small Relic Base",
  "Medium Relic": "Medium Relic Base",
  "Large Relic": "Large Relic Base",
};

/** Mutates `targets`, merging location names into each mapped target's
 * "Additional Names" field — port of parse.load_locations_into_targets. */
export function loadLocationsIntoTargets(
  locations: Map<string, string>,
  targets: Record<string, TargetEntry>,
): void {
  for (const [locationName, locationType] of locations) {
    const targetKey = LOCATION_TYPE_TO_TARGET_KEY[locationType];
    if (targetKey === undefined) {
      console.warn(`WARNING: location type ${locationType} not found in type key map`);
      continue;
    }
    const target = targets[targetKey];
    if (target === undefined) {
      console.warn(`WARNING: target key ${targetKey} not found in targets dictionary`);
      continue;
    }
    target["Additional Names"] =
      target["Additional Names"] === undefined
        ? locationName
        : target["Additional Names"] + ";" + locationName;
  }
}

export interface DataSnapshot {
  targets: Record<string, TargetEntry>;
  weapons: Record<string, WeaponEntry>;
  /** Mirrors parse.py's `all = weapons | targets`: weapons' keys first (in
   * weapons' insertion order), targets' keys override/append after — object
   * spread reproduces Python dict `|` union ordering exactly. */
  all: Record<string, Entity>;
  damages: Record<string, DamageTable>;
  bunkerStats: BunkerPieceTable;
  locations: Map<string, string>;
}

/** Loads data/*.json + Locations.csv from `dataDir` (the repo's data/
 * directory) into an immutable-in-spirit snapshot. No caching/singleton here
 * — data/dataStore.ts (Phase 3) owns the swappable "current snapshot"
 * concept; this function just does one load. */
export function loadDataSnapshot(dataDir: string): DataSnapshot {
  const targets = loadJson<Record<string, TargetEntry>>(dataDir, "Targets.json");
  const locations = loadLocationsFromCsv(dataDir);
  loadLocationsIntoTargets(locations, targets);

  const weapons = loadJson<Record<string, WeaponEntry>>(dataDir, "Weapons.json");
  const damages = loadJson<Record<string, DamageTable>>(dataDir, "Damage.json");
  const bunkerStats = loadJson<BunkerPieceTable>(dataDir, "Bunker_piece.json");

  return {
    targets,
    weapons,
    all: { ...weapons, ...targets },
    damages,
    bunkerStats,
    locations,
  };
}

/** Repo-root data/ directory, resolved relative to this file so it works
 * regardless of process cwd (unlike parse.py's cwd-relative "data/..."). */
export function defaultDataDir(): string {
  return path.resolve(fileURLToPath(import.meta.url), "../../../../data");
}
