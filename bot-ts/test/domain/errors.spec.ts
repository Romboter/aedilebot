import { describe, expect, it } from "vitest";
import {
  BunkerSpecParseError,
  NoDamageError,
  TargetNotFoundError,
  TargetOfTypeNotFoundError,
  WeaponNotFoundError,
} from "../../src/domain/errors.js";
import { loadFixtures } from "../fixtures.js";

interface CalculatorFixture {
  id: string;
  error?: string;
  message?: string;
}

describe("domain/errors parity with Python", () => {
  const fixtures = loadFixtures<CalculatorFixture[]>("calculator-fixtures.json");
  const byId = Object.fromEntries(fixtures.map((f) => [f.id, f]));

  it("matches TargetOfTypeNotFoundError text (disable on a non-vehicle)", () => {
    const err = new TargetOfTypeNotFoundError("Border base");
    expect(err.message).toBe(byId["disable_invalid_type"]?.message);
  });

  it("matches WeaponNotFoundError text", () => {
    const err = new WeaponNotFoundError("totally-not-a-real-weapon-xyz");
    expect(err.message).toBe(byId["error_weapon_not_found"]?.message);
  });

  it("matches TargetNotFoundError text", () => {
    const err = new TargetNotFoundError("totally-not-a-real-target-xyz");
    expect(err.message).toBe(byId["error_target_not_found"]?.message);
  });

  it("matches the zero-damage message format exactly", () => {
    const err = new NoDamageError("7.62mm", "DAE 3b-2 “Hades Net” (Unemplaced)");
    expect(err.message).toBe(byId["error_zero_damage"]?.message);
  });

  it("BunkerSpecParseError carries the documented example format", () => {
    const err = new BunkerSpecParseError("bad spec");
    expect(err.message).toContain("size 15 t3 bunker with 2 mg 3 atg 3 howi 1 ramp");
  });
});
