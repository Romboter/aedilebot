// domain/fuzzy's PluginHost<FuzzyApi> wrapper (Phase 3, goal C) — bundles
// match.ts + autocomplete.ts's exports into one api object, mirroring
// domain/calculator/plugin.ts. Grouped as one swappable unit because the
// plan lists "domain/fuzzy/*" as a single hot-swap area, not match.ts and
// autocomplete.ts separately.
//
// For this to actually change calculator behavior on a swap,
// domain/calculator/handlers.ts calls fuzzy matching through
// CalculatorContext.fuzzy (injected via buildCalculatorContext's second
// argument) rather than a static import — see handlers.ts's own comment.
import type { PluginModule } from "../../plugins/pluginHost.js";
import { autocompleteCandidates } from "./autocomplete.js";
import {
  fuzzyMatchAny,
  fuzzyMatchTargetName,
  fuzzyMatchWeaponName,
  fuzzyPerfectMatchAny,
  normalizedPartialRatioEqual,
  normalizedRatioEqual,
} from "./match.js";

export interface FuzzyApi {
  fuzzyMatchTargetName: typeof fuzzyMatchTargetName;
  fuzzyMatchWeaponName: typeof fuzzyMatchWeaponName;
  fuzzyMatchAny: typeof fuzzyMatchAny;
  fuzzyPerfectMatchAny: typeof fuzzyPerfectMatchAny;
  normalizedRatioEqual: typeof normalizedRatioEqual;
  normalizedPartialRatioEqual: typeof normalizedPartialRatioEqual;
  autocompleteCandidates: typeof autocompleteCandidates;
}

export const defaultFuzzyApi: FuzzyApi = {
  fuzzyMatchTargetName,
  fuzzyMatchWeaponName,
  fuzzyMatchAny,
  fuzzyPerfectMatchAny,
  normalizedRatioEqual,
  normalizedPartialRatioEqual,
  autocompleteCandidates,
};

async function validate(): Promise<void> {
  // Same live-data smoke-test pattern as domain/calculator/plugin.ts:
  // confirms a known weapon/target still resolves through the swapped-in
  // matching code, without asserting exact scores (fuzzball vs. any future
  // matching library can legitimately score differently — see
  // domain/fuzzy/match.ts's own header comment on this).
  const dataModule = (await import("../../data/dataStore.js")) as {
    default: PluginModule<import("../../data/loader.js").DataSnapshot>;
  };
  const { getAllNames } = await import("../../data/aliasIndex.js");
  const snapshot = dataModule.default.api;
  const weaponsDictionary = getAllNames(snapshot.weapons);
  const targetsDictionary = getAllNames(snapshot.targets);

  const weapon = fuzzyMatchWeaponName("40mm", weaponsDictionary);
  if (typeof weapon !== "string" || weapon.length === 0) {
    throw new Error("domain/fuzzy plugin validate: fuzzyMatchWeaponName could not resolve a known weapon (40mm)");
  }
  const target = fuzzyMatchTargetName("Border base", targetsDictionary, new Set(), true);
  if (typeof target.canonical !== "string" || target.canonical.length === 0) {
    throw new Error("domain/fuzzy plugin validate: fuzzyMatchTargetName could not resolve a known target (Border base)");
  }
  const suggestions = autocompleteCandidates("40mm", weaponsDictionary);
  if (suggestions.length === 0) {
    throw new Error("domain/fuzzy plugin validate: autocompleteCandidates returned nothing for a known weapon (40mm)");
  }
}

const fuzzyPlugin: PluginModule<FuzzyApi> = {
  version: new Date().toISOString(),
  validate,
  api: defaultFuzzyApi,
};

export default fuzzyPlugin;
