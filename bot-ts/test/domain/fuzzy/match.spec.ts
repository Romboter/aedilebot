import { beforeAll, describe, expect, it } from "vitest";
import { getAllNames, buildLocationNameIndex } from "../../../src/data/aliasIndex.js";
import { defaultDataDir, loadDataSnapshot } from "../../../src/data/loader.js";
import {
  fuzzyMatchAny,
  fuzzyMatchTargetName,
  fuzzyMatchWeaponName,
  fuzzyPerfectMatchAny,
  normalizedPartialRatioEqual,
  normalizedRatioEqual,
} from "../../../src/domain/fuzzy/match.js";
import { TargetNotFoundError, WeaponNotFoundError } from "../../../src/domain/errors.js";
import { normalize } from "../../../src/domain/normalize.js";
import { loadFixtures } from "../../fixtures.js";

interface WinnerFixture {
  kind: "target" | "weapon";
  query: string;
  source_name: string;
  canonical?: string;
  error?: string;
}

interface FuzzyFixture {
  id: string;
  kind: "weapon" | "target" | "husk" | "vehicle";
  query: string;
  canonical?: string;
  error?: string;
}

describe("domain/fuzzy/match", () => {
  const snapshot = loadDataSnapshot(defaultDataDir());
  const targetsDictionary = getAllNames(snapshot.targets);
  const weaponsDictionary = getAllNames(snapshot.weapons);
  const allDictionary = getAllNames(snapshot.all);
  const locationIndex = buildLocationNameIndex(snapshot.locations);

  describe("winner parity against 60 programmatic typo queries (ground truth from live Python)", () => {
    const fixtures = loadFixtures<WinnerFixture[]>("fuzzy-winner-fixtures.json");

    it.each(fixtures)("$kind: %j", (fixture) => {
      if (fixture.kind === "target") {
        const result = fuzzyMatchTargetName(fixture.query, targetsDictionary, locationIndex, true);
        expect(result.canonical).toBe(fixture.canonical);
      } else {
        const result = fuzzyMatchWeaponName(fixture.query, weaponsDictionary);
        expect(result).toBe(fixture.canonical);
      }
    });
  });

  describe("original fuzzy-fixtures.json cases", () => {
    const fixtures = loadFixtures<FuzzyFixture[]>("fuzzy-fixtures.json").filter(
      (f) => f.kind === "weapon" || f.kind === "target",
    );

    it.each(fixtures)("$id", (fixture) => {
      if (fixture.kind === "weapon") {
        expect(fuzzyMatchWeaponName(fixture.query, weaponsDictionary)).toBe(fixture.canonical);
      } else {
        expect(fuzzyMatchTargetName(fixture.query, targetsDictionary, locationIndex, true).canonical).toBe(
          fixture.canonical,
        );
      }
    });
  });

  it("throws TargetNotFoundError for gibberish", () => {
    expect(() => fuzzyMatchTargetName("zzzznotarealthingatall999", targetsDictionary, locationIndex, true)).toThrow(
      TargetNotFoundError,
    );
  });

  it("throws WeaponNotFoundError for gibberish", () => {
    expect(() => fuzzyMatchWeaponName("zzzznotarealthingatall999", weaponsDictionary)).toThrow(WeaponNotFoundError);
  });

  it("sets tokens.locationName to the normalized query for a known town/relic name", () => {
    // Python sets tokens["location_name"] = name AFTER name = utils.normalize(name)
    // at the top of the function, so it's the normalized form, not the raw input.
    const result = fuzzyMatchTargetName("finis", targetsDictionary, locationIndex, true);
    expect(result.tokens.locationName).toBe(normalize("finis"));
  });

  it("fuzzyMatchAny resolves a weapon and tags its type", () => {
    const result = fuzzyMatchAny("40mm", allDictionary, snapshot.all);
    expect(result.type).toBe("Weapons");
  });

  it("fuzzyMatchAny resolves a target and tags its type", () => {
    const result = fuzzyMatchAny("border base", allDictionary, snapshot.all);
    expect(result.type).toBe("Structures");
  });

  it("normalizedRatioEqual/normalizedPartialRatioEqual power the Watch Tower easter egg", () => {
    expect(normalizedRatioEqual("Watch Tower", "Watch Tower", 95)).toBe(true);
    expect(normalizedPartialRatioEqual("Scout Plane", "Scout Plane", 95)).toBe(true);
    expect(normalizedRatioEqual("40mm", "Watch Tower", 95)).toBe(false);
  });
});
