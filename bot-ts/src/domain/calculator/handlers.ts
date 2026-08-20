// Port of calculator.py's module-level handler functions (general_kill_handler,
// custom_kill_handler, general_disable_handler, general_dehusk_handler,
// general_bunker_kill_handler, command_bunker_kill_handler, statsheet_handler,
// easter_egg_check) — these are what bot.py's command/message handlers called.
// Bundles the data snapshot + alias dictionaries a caller needs into a single
// CalculatorContext instead of reaching into parse.py-style module globals.
//
// CalculatorContext.fuzzy is an injected FuzzyApi (defaulting to
// domain/fuzzy/plugin.ts's static implementation), not a hardcoded import of
// domain/fuzzy/match.ts — this is what makes a domain/fuzzy PluginHost swap
// (Phase 3) actually change calculator behavior, rather than the swap
// silently doing nothing because handlers.ts kept calling the old code.
import { buildLocationNameIndex, getAllNames, getHuskNames, getVehicleNames, isLocationName } from "../../data/aliasIndex.js";
import type { DataSnapshot } from "../../data/loader.js";
import { BunkerSpecParseError, EntityNotFoundError } from "../errors.js";
import type { FuzzyApi } from "../fuzzy/plugin.js";
import { defaultFuzzyApi } from "../fuzzy/plugin.js";
import { normalizedPartialRatioEqual, normalizedRatioEqual } from "../fuzzy/match.js";
import { parseBunkerSpec } from "../textParsing/bunkerSpecParser.js";
import type { BunkerSpec } from "./bunkerMath.js";
import type { DamageCalculatorArgs } from "./damageCalculator.js";
import { DamageCalculator } from "./damageCalculator.js";

export interface CalculatorContext {
  data: DataSnapshot;
  targetsDictionary: Map<string, string>;
  weaponsDictionary: Map<string, string>;
  huskDictionary: Map<string, string>;
  vehicleDictionary: Map<string, string>;
  allDictionary: Map<string, string>;
  locationNameIndex: Set<string>;
  /** Fuzzy-matching implementation, injected rather than statically
   * imported — this is what makes a domain/fuzzy PluginHost swap actually
   * observable through calculator handlers. Defaults to the current
   * built-in fuzzball-based implementation, so every existing call site
   * that doesn't care about hot-swap can keep calling
   * buildCalculatorContext(data) unchanged. */
  fuzzy: FuzzyApi;
}

export function buildCalculatorContext(data: DataSnapshot, fuzzy: FuzzyApi = defaultFuzzyApi): CalculatorContext {
  const targetsDictionary = getAllNames(data.targets);
  return {
    data,
    targetsDictionary,
    weaponsDictionary: getAllNames(data.weapons),
    huskDictionary: getHuskNames(targetsDictionary),
    vehicleDictionary: getVehicleNames(data.targets),
    allDictionary: getAllNames(data.all),
    locationNameIndex: buildLocationNameIndex(data.locations),
    fuzzy,
  };
}

function resolveWeaponName(ctx: CalculatorContext, weaponFuzzyName: string): string {
  return ctx.weaponsDictionary.get(weaponFuzzyName) ?? ctx.fuzzy.fuzzyMatchWeaponName(weaponFuzzyName, ctx.weaponsDictionary);
}

/** Direct-hit-or-fuzzy resolution shared by kill/dehusk/custom_kill against an
 * arbitrary targets-like dictionary, mirroring calculator.py's repeated
 * `if x in dict: ... else: fuzz.fuzzy_match_target_name(x, dict)` pattern. */
function resolveTargetName(
  ctx: CalculatorContext,
  targetsDictionary: Map<string, string>,
  targetFuzzyName: string,
  isDefaultDictionary: boolean,
): { targetName: string; args: DamageCalculatorArgs | undefined } {
  const direct = targetsDictionary.get(targetFuzzyName);
  if (direct !== undefined) {
    const args = isLocationName(targetFuzzyName, ctx.locationNameIndex) ? { locationName: targetFuzzyName } : undefined;
    return { targetName: direct, args };
  }
  const result = ctx.fuzzy.fuzzyMatchTargetName(targetFuzzyName, targetsDictionary, ctx.locationNameIndex, isDefaultDictionary);
  return { targetName: result.canonical, args: result.tokens };
}

// Deliberately still a static import, not routed through CalculatorContext:
// easter_egg_check runs before any dictionary/ctx is resolved in
// generalKillHandler (matching the Python original's own call order), and
// isn't itself a fuzzy *match* against the alias dictionaries — just two
// direct ratio/partial_ratio comparisons against a hardcoded pair. Not worth
// threading a ctx through for a whimsy feature with no data dependency.
export function easterEggCheck(weaponFuzzyName: string, targetFuzzyName: string): string | null {
  const easterEggs: Array<[weapon: string, target: string, hits: number, threshold: number]> = [
    ["Watch Tower", "Scout Plane", 1, 95],
  ];
  for (const [weapon, target, hits, threshold] of easterEggs) {
    if (normalizedRatioEqual(weaponFuzzyName, weapon, threshold) && normalizedPartialRatioEqual(targetFuzzyName, target, threshold)) {
      return `It takes ${hits} ${weapon} to kill a ${target}`;
    }
  }
  return null;
}

export function generalKillHandler(ctx: CalculatorContext, weaponFuzzyName: string, targetFuzzyName: string): string {
  const easterEgg = easterEggCheck(weaponFuzzyName, targetFuzzyName);
  if (easterEgg !== null) {
    return easterEgg;
  }
  const weaponName = resolveWeaponName(ctx, weaponFuzzyName);
  const { targetName, args } = resolveTargetName(ctx, ctx.targetsDictionary, targetFuzzyName, true);
  return new DamageCalculator(ctx.data, weaponName, targetName, args).getKillCalculation();
}

export function customKillHandler(
  ctx: CalculatorContext,
  weaponFuzzyName1: string,
  weapon1Hits: number,
  weaponFuzzyName2: string,
  targetFuzzyName: string,
): string {
  const weaponName1 = resolveWeaponName(ctx, weaponFuzzyName1);
  const weaponName2 = resolveWeaponName(ctx, weaponFuzzyName2);
  const { targetName, args } = resolveTargetName(ctx, ctx.targetsDictionary, targetFuzzyName, true);
  return new DamageCalculator(ctx.data, weaponName1, targetName, args, weaponName2, weapon1Hits).getCustomKillCalculation();
}

export function generalDisableHandler(ctx: CalculatorContext, weaponFuzzyName: string, targetFuzzyName: string): string {
  const weaponName = resolveWeaponName(ctx, weaponFuzzyName);
  const { targetName, args } = resolveTargetName(ctx, ctx.vehicleDictionary, targetFuzzyName, false);
  return new DamageCalculator(ctx.data, weaponName, targetName, args).getDisableCalculation();
}

export function generalDehuskHandler(ctx: CalculatorContext, weaponFuzzyName: string, targetFuzzyName: string): string {
  const weaponName = resolveWeaponName(ctx, weaponFuzzyName);
  const { targetName, args } = resolveTargetName(ctx, ctx.huskDictionary, targetFuzzyName, false);
  return new DamageCalculator(ctx.data, weaponName, targetName, args).getKillCalculation();
}

export function generalBunkerKillHandler(ctx: CalculatorContext, weaponFuzzyName: string, targetFuzzyText: string): string {
  const weaponName = resolveWeaponName(ctx, weaponFuzzyName);
  const bunkerSpec = parseBunkerSpec(targetFuzzyText);
  if (bunkerSpec === null) {
    throw new BunkerSpecParseError(targetFuzzyText);
  }
  return new DamageCalculator(ctx.data, weaponName, "meta", { bunkerSpec }).getKillCalculation();
}

export function commandBunkerKillHandler(ctx: CalculatorContext, weaponFuzzyName: string, bunkerSpec: BunkerSpec): string {
  const weaponName = resolveWeaponName(ctx, weaponFuzzyName);
  return new DamageCalculator(ctx.data, weaponName, "meta", { bunkerSpec }).getKillCalculation();
}

/** Port of statsheet_handler's own quirk: a bare `except` returns the
 * EntityNotFoundError instance instead of raising it, so this returns a union
 * rather than throwing on the not-found path — callers must check the type. */
export function statsheetHandler(ctx: CalculatorContext, entityName: string): Array<string | number> | EntityNotFoundError {
  try {
    const entity = ctx.fuzzy.fuzzyMatchAny(entityName, ctx.allDictionary, ctx.data.all);

    if (entity.type === "Weapons") {
      const weapon = ctx.data.weapons[ctx.fuzzy.fuzzyMatchWeaponName(entityName, ctx.weaponsDictionary)]!;
      return [weapon.ObjectType, weapon.Name, weapon.Damage, weapon.DamageType];
    }

    const target = ctx.data.targets[ctx.fuzzy.fuzzyMatchTargetName(entityName, ctx.targetsDictionary, ctx.locationNameIndex, true).canonical]!;

    if (target.ObjectType === "Structures") {
      return [
        target.ObjectType,
        target.Name,
        target.Health,
        target["Mitigation Type"],
        target.RepairCost,
        target.DecayStartHours,
        target.DecayDurationHours,
      ];
    }

    if (
      target.ObjectType === "Vehicles" ||
      target.ObjectType === "Aircraft_Parts" ||
      target.ObjectType === "Emplacements" ||
      target.ObjectType === "Tripods"
    ) {
      const minPenRaw = target["Min Base Penetration Chance"];
      const minPen = minPenRaw !== undefined ? Math.trunc(parseFloat(minPenRaw) * 100) : "";
      const maxPenRaw = target["Max Base Penetration Chance"];
      const maxPen = maxPenRaw !== undefined ? Math.trunc(parseFloat(maxPenRaw) * 100) : "";
      // "Armour Health" and "Reload time..." are read without a guard in the
      // Python original (a missing key there raises KeyError, caught by the
      // function's own outer except -> EntityNotFoundError) — replicated via
      // the same throw-and-catch here rather than silently defaulting.
      if (target["Armour Health"] === undefined || target["Reload time (pre-reload+reload) (magazine size) (artillery spread?)"] === undefined) {
        throw new Error("missing required vehicle-like field");
      }
      const armourHp = target["Armour Health"];
      const reload = target["Reload time (pre-reload+reload) (magazine size) (artillery spread?)"];
      const main = target["Main Weapon (damage bonus)(max range, reach)(artillery range)"] ?? "";
      const mainDisableRaw = target["Main Gun Disable Chance"];
      const mainDisable = mainDisableRaw !== undefined ? Math.trunc(parseFloat(mainDisableRaw) * 100) : "";
      const trackDisableRaw = target["Tracks Disable Chance"];
      const trackDisable = trackDisableRaw !== undefined ? Math.trunc(parseFloat(trackDisableRaw) * 100) : "";
      return [target.ObjectType, target.Name, target.Health, target["Mitigation Type"], minPen, maxPen, armourHp, reload, main, mainDisable, trackDisable];
    }

    if (target.ObjectType === "Multitier_structures") {
      return [target.ObjectType, target.Name, target.Health, target["Bmat cost"], target.RepairCost];
    }

    throw new Error(`unhandled ObjectType ${(target as { ObjectType: string }).ObjectType}`);
  } catch {
    return new EntityNotFoundError(entityName);
  }
}
