// Discriminated-union types for data/*.json, mirroring the current field
// variability by ObjectType 1:1 rather than collapsing it into one shape
// (see parse.py's raw dict access, calculator.py's ObjectType branching, and
// bot.py's statsheet ObjectType branching). Field names are kept as the raw
// JSON keys (including spaces/parens) so the data files are consumed byte-
// identical — no reshaping, per the rewrite plan. The real data has some
// sparse/inconsistent optional fields (confirmed by sampling all entries);
// those are typed optional rather than exhaustively modeling one-off data
// glitches (e.g. a single Vehicles entry with stray Structure-only fields).

export type TargetObjectType =
  | "Vehicles"
  | "Emplacements"
  | "Tripods"
  | "Aircraft_Parts"
  | "Structures"
  | "Multitier_structures";

/** Fields shared by Vehicles/Emplacements/Tripods/Aircraft_Parts — same shape,
 * only ObjectType differs, per the frequency scan of Targets.json. */
interface VehicleLikeFields {
  Name: string;
  Health: string;
  "Mitigation Type": string;
  /** Present for Vehicles/Emplacements/Aircraft_Parts; sparse (9/11) for
   * Tripods. get_disable_calculation only ever reads it for Vehicles/
   * Aircraft_Parts (other types raise InvalidTypeError first), so callers
   * must not assume presence. */
  "Disable Level"?: string;
  "Additional Names"?: string;
  "Dev Name"?: string;
  Cost?: string;
  "Repair Cost"?: string;
  Speed?: string;
  Slots?: string;
  "Armour Health"?: string;
  "Min Base Penetration Chance"?: string;
  "Max Base Penetration Chance"?: string;
  "Reload time (pre-reload+reload) (magazine size) (artillery spread?)"?: string;
  "Main Weapon (damage bonus)(max range, reach)(artillery range)"?: string;
  "Secondary Weapon"?: string;
  "Tracks Disable Chance"?: string;
  "Engine Disable Chance"?: string;
  "Main Gun Disable Chance"?: string;
  "Secondary Gun Disable Chance"?: string;
}

export interface VehicleEntry extends VehicleLikeFields {
  ObjectType: "Vehicles";
}
export interface EmplacementEntry extends VehicleLikeFields {
  ObjectType: "Emplacements";
}
export interface TripodEntry extends VehicleLikeFields {
  ObjectType: "Tripods";
}
export interface AircraftPartEntry extends VehicleLikeFields {
  ObjectType: "Aircraft_Parts";
}

export interface StructureEntry {
  ObjectType: "Structures";
  Name: string;
  Health: string;
  "Mitigation Type": string;
  RepairCost: string;
  DecayStartHours: string;
  DecayDurationHours: string;
  "Additional Names"?: string;
  "Dev Name"?: string;
  StructuralIntegrity?: string;
  /** Sparse cost-breakdown fields present on ~56% of entries; not read by
   * domain logic today, kept via index signature rather than enumerated. */
  [extra: string]: string | undefined;
}

export interface MultitierStructureEntry {
  ObjectType: "Multitier_structures";
  Name: string;
  Health: string;
  "Bmat cost": string;
  RepairCost: string;
  "Additional Names"?: string;
  "Dev Name"?: string;
  StoredItemCapacity?: string;
}

export type TargetEntry =
  | VehicleEntry
  | EmplacementEntry
  | TripodEntry
  | AircraftPartEntry
  | StructureEntry
  | MultitierStructureEntry;

export interface WeaponEntry {
  ObjectType: "Weapons";
  Name: string;
  "Dev Name": string;
  Damage: string;
  DamageType: string;
  "Additional Names"?: string;
}

/** Union of everything alias-indexable — mirrors parse.py's `all = weapons | targets`. */
export type Entity = TargetEntry | WeaponEntry;

/** data/Damage.json: keyed by damage type name, each entry maps mitigation-
 * type names (open-ended, dozens of values like "Tier1Structure", "Trench")
 * to a percentage string, plus its own "Name" key. Genuinely dynamic-keyed
 * data, not worth enumerating every mitigation type as its own field. */
export interface DamageTable {
  Name: string;
  [mitigationType: string]: string;
}

/** data/Bunker_piece.json: per-modification stats, arrays indexed by tier
 * (0=T1, 1=T2, 2=T3), matching calculator.py's `bunker_spec["tier"] - 1`. */
export interface BunkerPieceStats {
  health: [string, string, string];
  si: [string, string, string];
  repair: [string, string, string];
}

export type BunkerPieceTable = Record<string, BunkerPieceStats>;

/** data/Locations.csv rows: hex name, location name, location type
 * (no header row) — see parse.load_locations_from_csv. */
export interface LocationRow {
  hexName: string;
  locationName: string;
  locationType: string;
}
