import { describe, expect, it } from "vitest";
import { autocompleteCandidates } from "../../../src/domain/fuzzy/autocomplete.js";
import { getAllNames } from "../../../src/data/aliasIndex.js";
import { defaultDataDir, loadDataSnapshot } from "../../../src/data/loader.js";

describe("domain/fuzzy/autocomplete", () => {
  const snapshot = loadDataSnapshot(defaultDataDir());
  const weaponsDictionary = getAllNames(snapshot.weapons);
  const targetsDictionary = getAllNames(snapshot.targets);

  it("returns the exact-match canonical name first among candidates", () => {
    const result = autocompleteCandidates("40mm", weaponsDictionary);
    expect(result.map((c) => c.value)).toContain("40mm");
  });

  it("caps results at 20 and never repeats a canonical name", () => {
    const result = autocompleteCandidates("a", targetsDictionary, 5);
    expect(result.length).toBeLessThanOrEqual(20);
    expect(new Set(result.map((c) => c.value)).size).toBe(result.length);
  });

  it("returns nothing for gibberish below the score threshold", () => {
    expect(autocompleteCandidates("zzzznotarealthingatall999", weaponsDictionary)).toEqual([]);
  });

  it("name and value are always the same canonical string (plain-string Choice shape)", () => {
    const result = autocompleteCandidates("bord", targetsDictionary, 5);
    for (const choice of result) {
      expect(choice.name).toBe(choice.value);
    }
  });
});
