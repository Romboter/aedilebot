// Port of fuzzy.py's single-winner matchers (fuzzy_match_target_name,
// fuzzy_match_weapon_name, fuzzy_match_any, fuzzy_perfect_match_any) used by
// domain/calculator/handlers.ts to resolve a free-typed weapon/target name to
// its canonical dictionary entry.
//
// Uses `fuzzball` (a JS port of Python's fuzzywuzzy/TheFuzz) for ratio/
// partial_ratio/token_sort_ratio/token_set_ratio. Verified against 300 real
// (query, key) pairs from the actual game data: fuzzball's raw scores
// diverge from fuzzywuzzy's by a few points on ~8% of pairs (rounding/
// algorithm differences inside partial_ratio, not a bug in this port), so
// this module is validated on WHICH canonical name wins the match, not exact
// score values — matching the rewrite plan's own stated bar for fuzzy-match
// parity (see test/fixtures/fuzzy-scoring-fixtures.json and
// fuzzy-winner-fixtures.json).
import * as fuzzball from "fuzzball";
import {
  EntityNotFoundError,
  TargetNotFoundError,
  TargetOfTypeNotFoundError,
  WeaponNotFoundError,
} from "../errors.js";
import { normalize } from "../normalize.js";
import { isLocationName } from "../../data/aliasIndex.js";
import type { Entity } from "../../data/schema.js";

export interface TargetMatchTokens {
  locationName?: string;
}

export interface TargetMatchResult {
  canonical: string;
  tokens: TargetMatchTokens;
}

/** Single O(n) pass (plus a second O(n) pass only on a >100-score tie,
 * exactly like the Python original) over `targetsDictionary`. Not the O(n²)
 * autocomplete bug — that lived in bot.py's autocomplete callback re-calling
 * this function once per candidate; see domain/fuzzy/autocomplete.ts. */
export function fuzzyMatchTargetName(
  rawName: string,
  targetsDictionary: Map<string, string>,
  locationNameIndex: Set<string>,
  isDefaultDictionary: boolean,
): TargetMatchResult {
  const name = normalize(rawName);
  let maxScore = 0;
  let maxValue: string | undefined;
  let tieCount = 0;

  for (const [key, value] of targetsDictionary) {
    const score = fuzzball.token_set_ratio(name, key);
    if (score > maxScore) {
      maxScore = score;
      maxValue = value;
    }
    if (score === 100) {
      tieCount++;
    }
  }

  if (maxScore < 65 || maxValue === undefined) {
    throw isDefaultDictionary
      ? new TargetNotFoundError(name)
      : new TargetOfTypeNotFoundError(name);
  }

  const tokens: TargetMatchTokens = {};
  if (isLocationName(name, locationNameIndex)) {
    tokens.locationName = name;
  }

  if (tieCount > 1) {
    let tieBreakScore = 0;
    let tieBreakValue: string | undefined;
    for (const [key, value] of targetsDictionary) {
      const score = fuzzball.token_sort_ratio(name, key);
      if (score > tieBreakScore) {
        tieBreakScore = score;
        tieBreakValue = value;
      }
    }
    if (tieBreakValue !== undefined) {
      maxValue = tieBreakValue;
    }
  }

  return { canonical: maxValue, tokens };
}

export function fuzzyMatchWeaponName(rawName: string, weaponsDictionary: Map<string, string>): string {
  const name = normalize(rawName);
  let maxScore = 0;
  let maxValue: string | undefined;
  let tieCount = 0;

  for (const [key, value] of weaponsDictionary) {
    const score = fuzzball.token_set_ratio(name, key);
    if (score > maxScore) {
      maxScore = score;
      maxValue = value;
    }
    if (score === 100) {
      tieCount++;
    }
  }

  if (maxScore < 65 || maxValue === undefined) {
    throw new WeaponNotFoundError(name);
  }

  if (tieCount > 1) {
    let tieBreakScore = 0;
    let tieBreakValue: string | undefined;
    for (const [key, value] of weaponsDictionary) {
      const score = fuzzball.token_sort_ratio(name, key);
      if (score > tieBreakScore) {
        tieBreakScore = score;
        tieBreakValue = value;
      }
    }
    if (tieBreakValue !== undefined) {
      maxValue = tieBreakValue;
    }
  }

  return maxValue;
}

export interface AnyMatchResult {
  canonical: string;
  type: string;
}

/** Port of fuzzy_match_any: on multiple 100-scoring ties it delegates to
 * fuzzyPerfectMatchAny for a token_sort_ratio-based tie-break, same as
 * fuzzyMatchTargetName/fuzzyMatchWeaponName above but against the combined
 * targets+weapons dictionary. */
export function fuzzyMatchAny(
  rawName: string,
  allDictionary: Map<string, string>,
  allEntities: Record<string, Entity>,
): AnyMatchResult {
  const name = normalize(rawName);
  let maxScore = 0;
  let maxValue: string | undefined;
  let perfectCount = 0;

  for (const [key, value] of allDictionary) {
    const score = fuzzball.token_set_ratio(name, key);
    if (score > maxScore) {
      maxScore = score;
      maxValue = value;
    }
    if (score === 100) {
      perfectCount++;
    }
  }

  if (perfectCount > 1) {
    return fuzzyPerfectMatchAny(name, allDictionary, allEntities);
  }

  if (maxScore < 75 || maxValue === undefined) {
    throw new EntityNotFoundError(name);
  }

  return { canonical: maxValue, type: allEntities[maxValue]!.ObjectType };
}

export function fuzzyPerfectMatchAny(
  rawName: string,
  allDictionary: Map<string, string>,
  allEntities: Record<string, Entity>,
): AnyMatchResult {
  const name = normalize(rawName);
  let maxScore = 0;
  let maxValue: string | undefined;

  for (const [key, value] of allDictionary) {
    const score = fuzzball.token_sort_ratio(name, key);
    if (score > maxScore) {
      maxScore = score;
      maxValue = value;
    }
  }

  if (maxScore < 50 || maxValue === undefined) {
    throw new EntityNotFoundError(name);
  }

  return { canonical: maxValue, type: allEntities[maxValue]!.ObjectType };
}

/** Port of normalized_ratio_equal/normalized_partial_ratio_equal, used by
 * calculator.py's easter_egg_check. Default threshold matches Python's c=98. */
export function normalizedRatioEqual(a: string, b: string, threshold = 98): boolean {
  return fuzzball.ratio(normalize(a), normalize(b)) >= threshold;
}

export function normalizedPartialRatioEqual(a: string, b: string, threshold = 98): boolean {
  return fuzzball.partial_ratio(normalize(a), normalize(b)) >= threshold;
}
