// Loads the generated data layout (data/vehicles.json, structures.json, weapons.gen.json, ... plus data/overlay/*)
// and flattens it into the legacy DataSnapshot shape, so the calculator, statsheet and alias index keep working
// unchanged (docs/superpowers/specs/2026-11-08-data-layout-redesign.md, "Parity check" adapter). Delete this once the
// calculator reads typed rows directly.
//
// Keys, display Names and "Additional Names" are hand-curated, so they come from overlay/names.json (seeded from the old
// sheet by scripts/seed_names.py); every number comes from the generated files. Generated entries the overlay does not
// list (new game content) are appended under their generated name with no aliases.
import { readFileSync } from "node:fs";
import path from "node:path";
import type { DataSnapshot } from "./loader.js";
import { loadLocationsFromCsv, loadLocationsIntoTargets } from "./loader.js";
import type { BunkerPieceTable, DamageTable, Entity, TargetEntry, WeaponEntry } from "./schema.js";

interface Cost {
  code: string;
  qty: number;
}
interface GenWeaponRef {
  weapon: string | null;
  count: number;
  range: number;
  reach: number;
  firingTime: number;
  reload: number;
  magazine: number;
}
interface GenEntry {
  name: string;
  armourType?: string | null;
  health: number;
  repairCost: number;
  cost?: Cost[];
  armourHealth?: number;
  penetration?: { min: number; max: number };
  disableLevel?: number;
  disableChance?: { tracks: number; engine: number; mainGun: number; secondaryGun: number };
  slots?: number;
  mainWeapon?: GenWeaponRef | null;
  secondaryWeapon?: GenWeaponRef | null;
  weapon?: GenWeaponRef | null;
  emplaced?: { healthMultiplier: number };
  decay?: { startHours: number; durationHours: number };
  structuralIntegrity?: number;
  storedItemCapacity?: number;
}
interface GenWeapon {
  name: string;
  ammo: string | null;
  damage: number;
  damageType: string | null;
  shelterBonus: boolean;
}
interface NameEntry {
  from?: string;
  type?: string;
  name?: string;
  dev?: string;
  damageType?: string;
  variant?: "emplaced" | "unemplaced";
  aliases?: string;
  static?: Record<string, string>;
}
interface Names {
  targets: Record<string, NameEntry>;
  weapons: Record<string, NameEntry>;
}

type Row = Record<string, string>;

const COST_COLUMNS: Record<string, string> = {
  Wood: "Rmat cost",
  Cloth: "Bmat cost",
  Concrete: "Concrete cost",
  Excavation: "Shovel digs",
  SandbagMaterials: "Sandbag cost",
  BarbedWireMaterials: "Barbed wire cost",
  MetalBeamMaterials: "Metal beam cost",
};
const MAIN = "Main Weapon (damage bonus)(max range, reach)(artillery range)";
const RELOAD = "Reload time (pre-reload+reload) (magazine size) (artillery spread?)";

const str = (n: number | null | undefined): string => (n === null || n === undefined ? "" : String(n));

function readJson<T>(dataDir: string, file: string): T {
  return JSON.parse(readFileSync(path.join(dataDir, file), "utf-8")) as T;
}

function costColumns(cost: Cost[] | undefined): Row {
  const row: Row = {};
  for (const col of Object.values(COST_COLUMNS)) {
    row[col] = "0";
  }
  for (const c of cost ?? []) {
    const col = COST_COLUMNS[c.code];
    if (col !== undefined) {
      row[col] = String(c.qty);
    }
  }
  return row;
}

/** Statsheet text built from structured fields (the sheet's hand-formatted cells are not reproduced). */
function weaponText(w: GenWeaponRef | null | undefined, labels: Record<string, string>): string {
  if (!w) {
    return "";
  }
  const ammo = w.weapon?.split(":").pop() ?? "";
  const label = labels[ammo] ?? ammo;
  const reach = w.reach === w.range || w.reach === 0 ? `${w.range}m` : `${w.range}m, ${w.reach}m`;
  return `${w.count > 1 ? `${w.count}x ` : ""}${label} (${reach})`;
}

function reloadText(w: GenWeaponRef | null | undefined): string {
  if (!w) {
    return "";
  }
  return `${w.firingTime > 0 ? `${w.firingTime}s + ` : ""}${w.reload}s (${w.magazine}r)`;
}

export function loadNewSnapshot(dataDir: string): DataSnapshot {
  const names = readJson<Names>(dataDir, "overlay/names.json");
  const armourOverlay = readJson<Record<string, string>>(dataDir, "overlay/armour_types.json");
  const multitier = new Set(readJson<string[]>(dataDir, "overlay/multitier.json"));
  const labels = readJson<Record<string, string>>(dataDir, "overlay/ammo_labels.json");
  const files: Record<string, Record<string, GenEntry>> = {};
  for (const f of ["vehicles", "structures", "aircraft_parts", "emplacements", "tripods"]) {
    files[f] = readJson<Record<string, GenEntry>>(dataDir, `${f}.json`);
  }
  const genWeapons = readJson<Record<string, GenWeapon>>(dataDir, "weapons.gen.json");

  const common = (key: string, g: GenEntry, ne: NameEntry, dev: string): Row => ({
    Name: ne.name ?? g.name,
    "Additional Names": ne.aliases ?? "",
    "Dev Name": dev,
    Health: str(g.health),
    "Mitigation Type": g.armourType ?? armourOverlay[dev] ?? "",
  });

  const build = (file: string, dev: string, ne: NameEntry, key: string): TargetEntry => {
    const g = files[file]![dev]!;
    const type = ne.type ?? { vehicles: "Vehicles", structures: "Structures", aircraft_parts: "Aircraft_Parts", emplacements: "Emplacements", tripods: "Tripods" }[file]!;
    const row = common(key, g, ne, dev);
    if (file === "structures") {
      Object.assign(row, costColumns(g.cost), {
        RepairCost: str(g.repairCost),
        DecayStartHours: str(g.decay?.startHours),
        DecayDurationHours: str(g.decay?.durationHours),
        StructuralIntegrity: str(g.structuralIntegrity),
        StoredItemCapacity: str(g.storedItemCapacity),
        ObjectType: multitier.has(dev) ? "Multitier_structures" : type,
      });
    } else if (file === "aircraft_parts") {
      Object.assign(row, {
        "Armour Health": "0",
        "Min Base Penetration Chance": "1",
        "Max Base Penetration Chance": "1",
        "Disable Level": str(g.disableLevel),
        "Repair Cost": str(g.repairCost),
        ObjectType: "Aircraft_Parts",
      });
    } else if (file === "vehicles") {
      Object.assign(row, {
        "Armour Health": str(g.armourHealth),
        "Min Base Penetration Chance": str(g.penetration?.min),
        "Max Base Penetration Chance": str(g.penetration?.max),
        "Disable Level": str(g.disableLevel),
        "Repair Cost": str(g.repairCost),
        Slots: str(g.slots),
        [MAIN]: weaponText(g.mainWeapon, labels),
        [RELOAD]: reloadText(g.mainWeapon),
        "Secondary Weapon": weaponText(g.secondaryWeapon, labels),
        "Tracks Disable Chance": str(g.disableChance?.tracks),
        "Engine Disable Chance": str(g.disableChance?.engine),
        "Main Gun Disable Chance": str(g.disableChance?.mainGun),
        "Secondary Gun Disable Chance": str(g.disableChance?.secondaryGun),
        ObjectType: "Vehicles",
      });
    } else {
      // emplacements and tripods: no armour health or penetration in the game data
      const emplaced = ne.variant === "emplaced";
      row.Health = str(emplaced ? g.health * (g.emplaced?.healthMultiplier ?? 1) : g.health);
      Object.assign(row, {
        "Armour Health": "0",
        "Min Base Penetration Chance": "1",
        "Max Base Penetration Chance": "1",
        "Disable Level": "0",
        "Repair Cost": str(g.repairCost),
        [MAIN]: weaponText(g.weapon, labels),
        [RELOAD]: reloadText(g.weapon),
        ObjectType: type,
      });
    }
    return row as unknown as TargetEntry;
  };

  const targets: Record<string, TargetEntry> = {};
  const used = new Set<string>();
  for (const [key, ne] of Object.entries(names.targets)) {
    if (ne.static !== undefined) {
      targets[key] = ne.static as unknown as TargetEntry;
      continue;
    }
    const [file, dev] = ne.from!.split(":") as [string, string];
    used.add(ne.from!);
    targets[key] = build(file, dev, ne, key);
  }
  // generated entries the overlay does not know (new game content): appended, no aliases. Skipped when their name is already
  // a key or alias of anything (case-insensitive): the alias index lets later non-weapon entries overwrite, so a husk or
  // variant named like a real target ("Border Base") would hijack it.
  const taken = new Set<string>();
  for (const [k, t] of Object.entries(targets)) {
    for (const n of [k, t.Name, ...(t["Additional Names"] ?? "").split(";")]) taken.add(n.toLowerCase());
  }
  for (const [file, rows] of Object.entries(files)) {
    for (const dev of Object.keys(rows)) {
      if (!used.has(`${file}:${dev}`) && !taken.has(rows[dev]!.name.toLowerCase())) {
        taken.add(rows[dev]!.name.toLowerCase());
        targets[rows[dev]!.name] = build(file, dev, {}, rows[dev]!.name);
      }
    }
  }

  const weapons: Record<string, WeaponEntry> = {};
  for (const [key, ne] of Object.entries(names.weapons)) {
    if (ne.static !== undefined) {
      weapons[key] = ne.static as unknown as WeaponEntry;
      continue;
    }
    const g = genWeapons[ne.from!.slice("weapons:".length)]!;
    weapons[key] = {
      ObjectType: "Weapons",
      Name: ne.name ?? g.name,
      "Dev Name": ne.dev ?? g.ammo ?? "",
      Damage: String(g.damage),
      DamageType: g.damageType ?? ne.damageType ?? "",
      ShelterBonus: g.shelterBonus ? "TRUE" : "FALSE",
      "Additional Names": ne.aliases ?? "",
    };
  }

  const damageGen = readJson<Record<string, Record<string, number>>>(dataDir, "damage.gen.json");
  const damages: Record<string, DamageTable> = {};
  for (const [type, row] of Object.entries(damageGen)) {
    // "-" and "Nomitigation" are sheet-only columns the calculator still looks up
    damages[type] = { Name: type, "-": "None", ...Object.fromEntries(Object.entries(row).map(([m, v]) => [m, String(v)])), Nomitigation: "0" };
  }
  const bunkerGen = readJson<Record<string, { health: number[]; si: number[]; repair: number[] }>>(dataDir, "bunker_pieces.json");
  const bunkerStats: BunkerPieceTable = {};
  for (const [k, v] of Object.entries(bunkerGen)) {
    const s = (a: number[]): [string, string, string] => [String(a[0]), String(a[1]), String(a[2])];
    bunkerStats[k] = { health: s(v.health), si: s(v.si), repair: s(v.repair) };
  }

  const locations = loadLocationsFromCsv(dataDir, "locations.gen.csv");
  loadLocationsIntoTargets(locations, targets);
  return { targets, weapons, all: { ...weapons, ...targets } as Record<string, Entity>, damages, bunkerStats, locations };
}
