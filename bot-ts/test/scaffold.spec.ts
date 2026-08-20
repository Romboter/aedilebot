import { describe, expect, it } from "vitest";
import { loadFixtures } from "./fixtures.js";

// Proves the toolchain (vitest + fixture loading from repo root) works before
// any real domain code is ported. Delete once real calculator specs land.
describe("scaffold", () => {
  it("loads the golden fixtures generated from the Python calculator", () => {
    const fixtures = loadFixtures<unknown[]>("calculator-fixtures.json");
    expect(fixtures.length).toBeGreaterThan(0);
  });
});
