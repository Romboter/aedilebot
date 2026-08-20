// Port of calculator.py's DamageCalculator class — the core hits-to-kill/
// disable math. Takes a DataSnapshot instead of reaching into module-level
// parse.* globals (this rewrite's whole point is a swappable data snapshot),
// otherwise a straight behavior-preserving port.
import type { DataSnapshot } from "../../data/loader.js";
import type { DamageTable, TargetEntry, WeaponEntry } from "../../data/schema.js";
import { InvalidTypeError, NoDamageError } from "../errors.js";
import type { BunkerSpec } from "./bunkerMath.js";
import {
  calculateBreachableHealth,
  calculateBunkerHealth,
  calculateBunkerRepair,
  estimateRedGreen,
  getBunkerString,
  getBunkerWetMultiplier,
  getShelterBonus,
} from "./bunkerMath.js";
import { multitierDamageCalculator } from "./multitier.js";

// calculate_hits_to_reach_health
function calculateHitsToReachHealth(health: number, damage: number): number {
  return Math.ceil(health / damage);
}

// main.clean_capitalize: capitalize each whitespace-split word, dropping
// extra whitespace — not the same as CSS text-transform (each word is
// title-cased from a fully-lowercased rest, not just its first letter).
function cleanCapitalize(str: string): string {
  const words = str.split(/\s+/).filter((w) => w.length > 0);
  if (words.length === 0) {
    return str;
  }
  return words.map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");
}

// Hardcoded Dev Name list for the impact-fuse low-roll adjustment (foxhole's
// non-hitscan weapons can land as low as ~95% damage) — preserved verbatim.
const IMPACT_FUSE_DEV_NAMES = new Set([
  "ATRPGLightCAmmo",
  "ATRPGAmmo",
  "ATRPGIndirectAmmo",
  "RpgAmmo",
  "HELaunchedGrenade",
  "ATLaunchedGrenadeW",
  "ATGrenadeW",
  "StickyBomb",
  "MortarTankAmmo",
  "HEGrenade",
]);

const LOW_ROLL_DISABLE_DAMAGE_TYPES = new Set([
  "AntiTankExplosive",
  "Explosive",
  "HighExplosive",
  "ArmourPiercing",
  "Demolition",
]);

export interface DamageCalculatorArgs {
  locationName?: string;
  emplaced?: boolean;
  veterancy?: unknown;
  devastation?: unknown;
  bunkerSpec?: BunkerSpec;
}

export class DamageCalculator {
  private readonly data: DataSnapshot;

  readonly weaponName: string;
  readonly targetName: string;
  readonly weaponName2?: string;
  readonly weapon1Hits?: number;

  weapon: WeaponEntry;
  target: "meta" | TargetEntry;
  targetType: string;
  health: number | null;
  damageValue: number;
  damageType: DamageTable;

  maxHitsToKill = -1;
  minRealDamage = -1;
  shelters = 0;
  mitigationType: string | null = null;
  dmgMultiplier: number | null = null;

  locationName?: string;
  emplaced?: boolean;
  veterancy?: unknown;
  devastation?: unknown;

  estimated?: boolean;
  si?: number;
  rawHealth?: number;
  breachableHealth?: number;
  repairCost?: number;
  bunkerString?: string;

  constructor(
    data: DataSnapshot,
    weaponName: string,
    targetName: string,
    args?: DamageCalculatorArgs,
    weaponName2?: string,
    weapon1Hits?: number,
  ) {
    this.data = data;
    this.weaponName = weaponName;
    this.targetName = targetName;
    this.weaponName2 = weaponName2;
    this.weapon1Hits = weapon1Hits;
    this.weapon = data.weapons[weaponName]!;

    if (targetName === "meta") {
      this.target = "meta";
      this.targetType = "Structures";
      this.health = null;
    } else {
      const target = data.targets[targetName]!;
      this.target = target;
      this.targetType = target.ObjectType;
      this.health = parseFloat(target.Health);
    }

    this.damageValue = parseFloat(this.weapon.Damage);
    this.damageType = { ...data.damages[this.weapon.DamageType]! };

    if (args === undefined) {
      return;
    }
    if (args.locationName !== undefined) {
      this.locationName = args.locationName;
    }
    if (args.emplaced !== undefined) {
      this.emplaced = args.emplaced;
    }
    if (args.veterancy !== undefined) {
      this.veterancy = args.veterancy;
    }
    if (args.devastation !== undefined) {
      this.devastation = args.devastation;
    }
    if (args.bunkerSpec !== undefined) {
      const spec = args.bunkerSpec;
      if (spec.red === undefined || spec.green === undefined || spec.red === -1 || spec.green === -1) {
        if (spec.red !== undefined && spec.red !== -1) {
          spec.green = Math.floor((spec.size * 4 - spec.red) / 2);
        } else if (spec.green !== undefined && spec.green !== -1) {
          spec.red = spec.size * 4 - spec.green * 2;
        } else {
          const estimate = estimateRedGreen(spec.size);
          spec.green = estimate.green;
          spec.red = estimate.red;
        }
        this.estimated = true;
      } else {
        this.estimated = false;
      }
      if (spec.shelter !== undefined) {
        this.shelters = spec.shelter;
      }

      const result = calculateBunkerHealth(spec, data.bunkerStats);
      this.mitigationType = result.mitigationType;
      this.si = result.si;
      this.rawHealth = result.rawHealth;
      this.health = result.health;
      this.breachableHealth = calculateBreachableHealth(this.rawHealth, this.si);
      this.dmgMultiplier = getBunkerWetMultiplier(spec.wet);
      this.repairCost = calculateBunkerRepair(spec, data.bunkerStats);
      this.bunkerString = getBunkerString(spec, data.bunkerStats, {
        health: this.health,
        repairCost: this.repairCost,
        si: this.si,
        estimated: this.estimated,
      });
    }
  }

  calculateDamage(mitigationType?: string): number {
    // Reached without an explicit mitigationType only for target types that
    // do carry "Mitigation Type" (Multitier_structures always passes an
    // explicit tier name via multitierDamageCalculator instead) — cast past
    // the discriminated union rather than widening TargetEntry itself.
    const mt = mitigationType ?? this.mitigationType ?? (this.target as { "Mitigation Type": string })["Mitigation Type"];
    const mitigationValue = parseFloat(this.damageType[mt]!);
    let realDamage = this.damageValue * (1 - mitigationValue);
    if (this.dmgMultiplier !== null) {
      realDamage *= this.dmgMultiplier;
    }
    if (realDamage === 0) {
      throw new NoDamageError(this.weaponName, this.targetName);
    }
    if (this.shelters > 0 && (this.damageType.Name === "HighExplosive" || this.damageType.Name === "IncendiaryHighExplosive")) {
      const mitigationBonus = getShelterBonus(this.shelters);
      const maxMitigationValue = parseFloat(this.damageType[mt]!) + mitigationBonus;
      this.minRealDamage = Math.ceil(this.damageValue * (1 - maxMitigationValue));
    }
    return Math.ceil(realDamage);
  }

  getShelterBonus(shelters: number): number {
    return getShelterBonus(shelters);
  }

  getDisableHealth(): number {
    const target = this.target as "meta" | (TargetEntry & { "Disable Level"?: string });
    if (target !== "meta" && target["Disable Level"] !== undefined) {
      return this.health! * (1.005 - parseFloat(target["Disable Level"]));
    }
    throw new InvalidTypeError(this.targetName);
  }

  // Considers low-roll possibility (impact-fuse weapons) and shelter bonus:
  // returns a single hit count, or a "min to max" range string.
  generalDamageCalculator(): string | number {
    const maxDamage = this.calculateDamage();
    const minHitsToKill = calculateHitsToReachHealth(this.health!, maxDamage);
    if (this.minRealDamage > 0) {
      this.maxHitsToKill = calculateHitsToReachHealth(this.health!, this.minRealDamage);
    }
    if (IMPACT_FUSE_DEV_NAMES.has(this.weapon["Dev Name"] ?? "")) {
      this.maxHitsToKill = Math.max(this.maxHitsToKill, calculateHitsToReachHealth(this.health!, maxDamage * 0.95));
    }
    if (this.maxHitsToKill > minHitsToKill) {
      return `${minHitsToKill} to ${this.maxHitsToKill}`;
    }
    return minHitsToKill;
  }

  multitierDamageCalculator(): string {
    return multitierDamageCalculator(this.health!, (mitigationType) => this.calculateDamage(mitigationType));
  }

  private hitsToKillForTargetType(): string | number {
    if (this.targetType === "Vehicles" || this.targetType === "Aircraft_Parts") {
      return this.generalDamageCalculator();
    }
    if (this.targetType === "Multitier_structures") {
      return this.multitierDamageCalculator();
    }
    if (this.targetType === "Emplacements") {
      return this.generalDamageCalculator();
    }
    if (this.targetType === "Tripods" || this.targetType === "Structures") {
      return this.generalDamageCalculator();
    }
    throw new InvalidTypeError(
      this.targetName,
      "There was an unexpected error trying to find the entity. Please contact the developers.",
    );
  }

  private displayName(): string {
    return this.locationName ? `${cleanCapitalize(this.locationName)} (${this.targetName})` : this.targetName;
  }

  getKillCalculation(): string {
    const hitsToKill = this.hitsToKillForTargetType();
    let retStr = `It takes ${hitsToKill} ${this.weaponName} to kill a ${this.displayName()}`;
    if (this.target === "meta") {
      retStr += this.bunkerString!;
    }
    return retStr;
  }

  getCustomKillCalculation(): string {
    const remainingHealth = this.health! - this.weapon1Hits! * this.calculateDamage();
    if (remainingHealth <= 0) {
      return this.getKillCalculation();
    }

    this.health = remainingHealth;
    this.weapon = this.data.weapons[this.weaponName2!]!;
    this.damageValue = parseFloat(this.weapon.Damage);
    this.damageType = this.data.damages[this.weapon.DamageType]!;

    const hitsToKill = this.hitsToKillForTargetType();
    let retStr =
      `It takes ${hitsToKill} ${this.weaponName2} to kill a ${this.displayName()} after ` +
      `${this.weapon1Hits} ${this.weaponName} hits.`;
    if (this.target === "meta") {
      retStr += this.bunkerString!;
    }
    return retStr;
  }

  getDisableCalculation(): string {
    if (this.targetType !== "Vehicles" && this.targetType !== "Aircraft_Parts") {
      throw new InvalidTypeError(this.targetName);
    }
    const finalDamage = this.calculateDamage();
    let minHitsToDisable: string | number = calculateHitsToReachHealth(this.getDisableHealth(), finalDamage);
    if (LOW_ROLL_DISABLE_DAMAGE_TYPES.has(this.weapon.DamageType)) {
      const maxHits = calculateHitsToReachHealth(this.getDisableHealth(), finalDamage * 0.95);
      minHitsToDisable = minHitsToDisable < maxHits ? `${minHitsToDisable} to ${maxHits}` : minHitsToDisable;
    }
    return `It takes ${minHitsToDisable} ${this.weaponName} to disable a ${this.targetName}`;
  }
}
