import { describe, expect, it } from "vitest";
import { estimateRedGreen, getBunkerWetMultiplier, getShelterBonus } from "../../../src/domain/calculator/bunkerMath.js";

describe("domain/calculator/bunkerMath sub-functions", () => {
  it("getBunkerWetMultiplier: hours=0 is a special-cased 10, not a division by zero", () => {
    expect(getBunkerWetMultiplier(0)).toBe(10);
  });

  it("getBunkerWetMultiplier: clamps to [1, 10]", () => {
    expect(getBunkerWetMultiplier(1)).toBe(10); // 24/1=24 clamped down to 10
    expect(getBunkerWetMultiplier(24)).toBe(1); // 24/24=1
    expect(getBunkerWetMultiplier(48)).toBe(1); // 24/48=0.5 clamped up to 1
    expect(getBunkerWetMultiplier(12)).toBe(2); // 24/12=2, inside the clamp
  });

  it("estimateRedGreen: perfect square piece count", () => {
    expect(estimateRedGreen(9)).toEqual({ green: 12, red: 12 });
  });

  it("estimateRedGreen: imperfect rectangle estimates more red", () => {
    expect(estimateRedGreen(15)).toEqual({ green: 22, red: 16 });
    expect(estimateRedGreen(10)).toEqual({ green: 13, red: 14 });
  });

  it("getShelterBonus: geometric decay per shelter, capped at 9", () => {
    expect(getShelterBonus(0)).toBeCloseTo(0);
    expect(getShelterBonus(1)).toBeCloseTo(0.15);
    expect(getShelterBonus(2)).toBeCloseTo(0.15 + 0.0375);
    expect(getShelterBonus(9)).toBe(getShelterBonus(20)); // capped at 9 shelters
  });
});
