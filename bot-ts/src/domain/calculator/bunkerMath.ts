// Port of calculator.py's bunker-piece math (DamageCalculator.estimate_red_green,
// get_bunker_wet_multipler, calculate_bunker_health, calculate_breachable_health,
// calculate_bunker_repair, get_shelter_bonus, get_bunker_string). Pure functions
// over a BunkerSpec + the Bunker_piece.json table, no discord.js dependency.
//
// BunkerSpec key iteration order matters for get_bunker_string's mod listing —
// it mirrors Python dict insertion order exactly (JS object property order for
// non-numeric-string keys), so callers must build/mutate specs the same way
// Python did (see domain/textParsing/bunkerSpecParser.ts and
// domain/calculator/damageCalculator.ts's constructor).
import type { BunkerPieceTable } from "../../data/schema.js";

export type BunkerSpec = { size: number; tier: number; wet: number } & Record<string, number>;

const TIER_WORDS: Record<number, string> = { 1: "tier 1", 2: "tier 2", 3: "tier 3" };

export function estimateRedGreen(pieceNum: number): { green: number; red: number } {
  const width = Math.floor(Math.sqrt(pieceNum));
  const height = Math.ceil(pieceNum / width);
  const externalEdges = 2 * (width + height);
  const totalEdges = 4 * pieceNum;
  const internalEdges = Math.floor((totalEdges - externalEdges) / 2);
  return { green: internalEdges, red: externalEdges };
}

export function getBunkerWetMultiplier(hours: number): number {
  if (hours === 0) {
    return 10;
  }
  return Math.max(Math.min(24 / hours, 10), 1);
}

export interface BunkerHealthResult {
  rawHealth: number;
  si: number;
  mitigationType: string;
  health: number;
}

export function calculateBunkerHealth(spec: BunkerSpec, bunkerStats: BunkerPieceTable): BunkerHealthResult {
  const tierToMitigation: Record<number, string> = { 0: "Tier1Structure", 1: "Tier2Structure", 2: "Tier3Structure" };
  let empty = spec.size;
  const tier = spec.tier - 1;
  let rawHealth = 0;
  let si = 1;
  for (const mod of Object.keys(spec)) {
    const stats = bunkerStats[mod];
    if (stats !== undefined) {
      const count = spec[mod]!;
      rawHealth += parseFloat(stats.health[tier]!) * count;
      empty -= count;
      si *= parseFloat(stats.si[tier]!) ** count;
    }
  }
  rawHealth += parseFloat(bunkerStats.piece!.health[tier]!) * empty;
  si *= parseFloat(bunkerStats.piece!.si[tier]!) ** empty;
  if (spec.size === 1) {
    si = 1;
  }
  const mitigationType = tierToMitigation[tier]!;
  const green = spec.green ?? 0;
  const red = spec.red ?? 0;
  if (green + red > 0) {
    si = si + Math.min(si, (0.15 * green) / (green + red));
  }
  return { rawHealth, si, mitigationType, health: rawHealth * si };
}

export function calculateBreachableHealth(rawHealth: number, si: number): number {
  return rawHealth * (1 - si);
}

export function calculateBunkerRepair(spec: BunkerSpec, bunkerStats: BunkerPieceTable): number {
  let repair = 0;
  let empty = spec.size;
  const tier = spec.tier - 1;
  for (const mod of Object.keys(spec)) {
    const stats = bunkerStats[mod];
    if (stats !== undefined) {
      const count = spec[mod]!;
      repair += parseFloat(stats.repair[tier]!) * count;
      empty -= count;
    }
  }
  repair += parseFloat(bunkerStats.piece!.repair[tier]!) * empty;
  return repair;
}

export function getShelterBonus(shelters: number): number {
  const capped = Math.min(9, shelters);
  let bonus = 0.15;
  let total = 0;
  for (let i = 0; i < capped; i++) {
    total += bonus;
    bonus /= 4;
  }
  return total;
}

export interface BunkerStringOptions {
  health: number;
  repairCost: number;
  si: number;
  estimated: boolean;
}

export function getBunkerString(spec: BunkerSpec, bunkerStats: BunkerPieceTable, opts: BunkerStringOptions): string {
  let modStr = "";
  for (const mod of Object.keys(spec)) {
    if (bunkerStats[mod] !== undefined && spec[mod] !== 0) {
      modStr += `${spec[mod]} ${mod}, `;
    }
    if (mod === "red" || mod === "green") {
      modStr += `${spec[mod]} ${mod}, `;
    }
  }
  modStr = `(${TIER_WORDS[spec.tier]}, ${spec.size} pieces, ${modStr.slice(0, -2)})`;
  const repairRatio = (opts.health / opts.repairCost).toFixed(2);
  const breachablePercent = ((1 - opts.si) * 100).toFixed(2);
  const healthAndRepair =
    `**${Math.ceil(opts.health)} health** (${breachablePercent}% breachable) and ` +
    `**${Math.ceil(opts.repairCost)} bmat repair cost** (${repairRatio} health/bmat)`;
  let ret = ` with ${healthAndRepair} ${modStr}`;
  if (spec.wet >= 0 && spec.wet < 24) {
    ret = ` that is ${spec.wet} hour wet${ret}`;
  }
  if (opts.estimated) {
    ret += " (red or green estimated due to not being specified)";
  }
  return ret;
}
