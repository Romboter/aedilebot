import { describe, expect, it } from "vitest";
import { defaultDataDir, loadDataSnapshot } from "../../src/data/loader.js";
import { buildCalculatorContext, generalDehuskHandler, generalDisableHandler, generalKillHandler } from "../../src/domain/calculator/handlers.js";
import { loadFixtures } from "../fixtures.js";
import { loadNewSnapshot } from "../../src/data/newLoader.js";

const legacy = loadDataSnapshot(defaultDataDir());
const generated = loadNewSnapshot(defaultDataDir());

// Differences between the old hand sheet and the generated data are expected where the game export beats the sheet
// (docs/data-parity-scope.md); these tests pin that the generated snapshot is structurally the same and report the rest.
describe("generated data layout parity", () => {
  it("has every legacy target and weapon key, with the same ObjectType", () => {
    const missing = Object.keys(legacy.targets).filter((k) => generated.targets[k] === undefined);
    expect(missing).toEqual([]);
    expect(Object.keys(legacy.weapons).filter((k) => generated.weapons[k] === undefined)).toEqual([]);
    const typeDiff = Object.entries(legacy.targets).filter(([k, v]) => generated.targets[k]!.ObjectType !== v.ObjectType);
    expect(typeDiff.map(([k]) => k)).toEqual([]);
  });

  it("reports numeric field differences", () => {
    const diffs: Record<string, string[]> = {};
    for (const [k, v] of Object.entries(legacy.targets)) {
      const g = generated.targets[k] as unknown as Record<string, string>;
      for (const f of ["Health", "Mitigation Type", "RepairCost", "Repair Cost", "DecayStartHours", "DecayDurationHours", "Disable Level", "Armour Health", "Slots"]) {
        const a = (v as unknown as Record<string, string>)[f];
        if (a === undefined || a === "" || g[f] === undefined) continue;
        const same = a === g[f] || (a !== "" && !Number.isNaN(parseFloat(a)) && Math.abs(parseFloat(a) - parseFloat(g[f]!)) < 1e-4);
        if (!same) (diffs[f] ??= []).push(`${k}: ${a} -> ${g[f]}`);
      }
    }
    for (const w of Object.keys(legacy.weapons)) {
      const a = legacy.weapons[w]!, g = generated.weapons[w]!;
      for (const f of ["Damage", "DamageType"] as const) {
        if (a[f] !== g[f] && !(f === "Damage" && Math.abs(parseFloat(a[f]) - parseFloat(g[f])) < 1e-3 * parseFloat(a[f]))) (diffs[`weapon ${f}`] ??= []).push(`${w}: ${a[f]} -> ${g[f]}`);
      }
    }
    console.log(Object.fromEntries(Object.entries(diffs).map(([f, d]) => [f, `${d.length}: ${d.slice(0, 6).join(" | ")}`])));
    // the documented sheet errors (docs/data-parity-scope.md); a new difference here is a regression or new sheet error
    expect(Object.fromEntries(Object.entries(diffs).map(([f, d]) => [f, d.length]))).toEqual({
      "Disable Level": 1, Health: 6, DecayStartHours: 45, DecayDurationHours: 43, RepairCost: 12, "Repair Cost": 1,
      // 6 game-data differences plus 6 native-class armour types corrected from the wiki structures table
      // (Keep, Emplacement House, three bridges, Barbed Wire Fence); the game files do not hold these values
      "Mitigation Type": 12, Slots: 6, "weapon Damage": 2,
    });
  });

  it("answers the kill/disable/dehusk fixtures the same way", () => {
    const old = buildCalculatorContext(legacy);
    const gen = buildCalculatorContext(generated);
    const fixtures = loadFixtures<Array<{ id: string; operation: string; input: unknown[]; error?: string }>>("calculator-fixtures.json")
      .filter((f) => ["kill", "disable", "dehusk"].includes(f.operation) && f.error === undefined);
    const handler = { kill: generalKillHandler, disable: generalDisableHandler, dehusk: generalDehuskHandler } as const;
    const differ: string[] = [];
    for (const f of fixtures) {
      const h = handler[f.operation as keyof typeof handler];
      const [a, b] = f.input as [string, string];
      let x: unknown, y: unknown;
      try { x = h(old, a, b); } catch (e) { x = String(e); }
      try { y = h(gen, a, b); } catch (e) { y = String(e); }
      if (JSON.stringify(x) !== JSON.stringify(y)) differ.push(`${f.id}: ${JSON.stringify(x)} vs ${JSON.stringify(y)}`);
    }
    expect({ total: fixtures.length, differ }).toEqual({ total: fixtures.length, differ: [] });
  });
});
