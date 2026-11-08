import { describe, expect, it } from "vitest";
import { DamageCalculator } from "../../../src/domain/calculator/damageCalculator.js";
import { defaultDataDir, loadDataSnapshot } from "../../../src/data/loader.js";

// minRealDamage is only set when the weapon's ShelterBonus flag (the game's bAffectedByShelterBonus) is TRUE.
describe("shelter bonus follows the generated ShelterBonus flag", () => {
  const data = loadDataSnapshot(defaultDataDir());
  const minReal = (weapon: string) => {
    const calc = new DamageCalculator(data, weapon, "Rifle Pillbox");
    calc.shelters = 3;
    calc.calculateDamage();
    return calc.minRealDamage;
  };

  it("applies to HighExplosive", () => expect(minReal("Mortar Shell")).not.toBe(-1));
  it("applies to bombs the game flags (BombHighExplosive)", () => expect(minReal("Mark II Raidbreaker")).not.toBe(-1));
  it("does not apply to the HighExplosive breaching-leak 300mm (flag FALSE)", () => expect(minReal("300mm")).toBe(-1));
});
