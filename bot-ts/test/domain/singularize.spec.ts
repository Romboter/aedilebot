import { describe, expect, it } from "vitest";
import { singularize } from "../../src/domain/normalize.js";
import { loadFixtures } from "../fixtures.js";

describe("domain/normalize singularize parity with Python inflect", () => {
  const fixtures = loadFixtures<Record<string, string>>("singularize-fixtures.json");
  const entries = Object.entries(fixtures);

  it(`matches inflect on all ${entries.length} words from the real game data`, () => {
    const mismatches = entries
      .map(([word, expected]) => [word, expected, singularize(word)] as const)
      .filter(([, expected, got]) => expected !== got);
    expect(mismatches).toEqual([]);
  });
});
