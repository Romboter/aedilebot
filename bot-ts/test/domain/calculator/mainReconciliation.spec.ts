import { describe, expect, it } from "vitest";
import { getAllNames } from "../../../src/data/aliasIndex.js";
import { defaultDataDir, loadDataSnapshot } from "../../../src/data/loader.js";
import { DamageCalculator } from "../../../src/domain/calculator/damageCalculator.js";

// Regressions for the three Python main commits merged in issue #22.
describe("September Python-main reconciliation", () => {
  const snapshot = loadDataSnapshot(defaultDataDir());

  it("includes the new T2/T3 anti-tank and rifle garrison ammunition", () => {
    expect(snapshot.weapons["T2 ATG Shell"]?.["Dev Name"]).toBe("ATGT2Ammo");
    expect(snapshot.weapons["T3 ATG Shell"]?.["Dev Name"]).toBe("ATGT3Ammo");
    expect(snapshot.weapons["Rifle Garrison ammo"]?.Damage).toBe("50.0");
  });

  it("routes the unqualified atg and rg aliases to the new weapons", () => {
    const names = getAllNames(snapshot.weapons);
    expect(names.get("atg")).toBe("T3 ATG Shell");
    expect(names.get("rg")).toBe("Rifle Garrison ammo");
    expect(names.get("mg garrison")).toBe("12.7mm");
  });

  it("uses a 94% impact-fuse low roll instead of the previous 95%", () => {
    const calculator = new DamageCalculator(snapshot, "RPG", "Border base");
    const fullDamage = calculator.calculateDamage();
    // 94.5% of nominal damage is below a 95% low roll but above 94%.
    // The old multiplier returned one hit; the new multiplier returns 1 to 2.
    calculator.health = fullDamage * 0.945;
    expect(calculator.generalDamageCalculator()).toBe("1 to 2");
  });
});
