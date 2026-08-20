import { describe, expect, it } from "vitest";
import { buildCalculatorContext, generalKillHandler } from "../../../src/domain/calculator/handlers.js";
import { defaultFuzzyApi } from "../../../src/domain/fuzzy/plugin.js";
import type { FuzzyApi } from "../../../src/domain/fuzzy/plugin.js";
import { defaultDataDir, loadDataSnapshot } from "../../../src/data/loader.js";

// Proves CalculatorContext.fuzzy is a real seam, not just a type-level no-op:
// swapping in a stub fuzzy implementation changes generalKillHandler's
// behavior even though the underlying data/dictionaries are untouched. This
// is what makes a domain/fuzzy PluginHost swap (Phase 3) actually observable
// through the calculator, rather than handlers.ts silently keeping the old
// hardcoded import.
describe("domain/calculator/handlers.ts fuzzy injection seam", () => {
  const snapshot = loadDataSnapshot(defaultDataDir());

  it("default fuzzy (no second arg) behaves exactly as before", () => {
    const ctx = buildCalculatorContext(snapshot);
    expect(generalKillHandler(ctx, "150mm", "Border base")).toBe("It takes 12 150mm to kill a Border base");
  });

  it("a stub FuzzyApi that always resolves weapons to a fixed name changes the handler's output", () => {
    const stubFuzzy: FuzzyApi = {
      ...defaultFuzzyApi,
      fuzzyMatchWeaponName: () => "300mm",
    };
    const ctx = buildCalculatorContext(snapshot, stubFuzzy);

    // "totally-not-a-real-weapon" isn't in the weapons dictionary at all, so
    // this can only resolve via the stub's fuzzy matcher, not a direct hit -
    // proving resolveWeaponName actually calls ctx.fuzzy, not the real one.
    const result = generalKillHandler(ctx, "totally-not-a-real-weapon", "Border base");
    expect(result).toContain("300mm");
  });
});
