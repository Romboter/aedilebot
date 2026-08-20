import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { describe, expect, it } from "vitest";
import type { TargetEntry, WeaponEntry } from "../../src/data/schema.js";

// Reads the raw data files directly (data/loader.ts doesn't exist yet) just
// to confirm the schema's discriminant literals actually match what's in the
// real JSON, and that TS narrowing behaves as expected on real entries.
const repoRoot = path.resolve(fileURLToPath(import.meta.url), "../../../..");

function loadJson<T>(relPath: string): T {
  return JSON.parse(readFileSync(path.join(repoRoot, relPath), "utf-8")) as T;
}

describe("data/schema matches real data files", () => {
  const targets = loadJson<Record<string, TargetEntry>>("data/Targets.json");
  const weapons = loadJson<Record<string, WeaponEntry>>("data/Weapons.json");

  it("every target ObjectType present in the data is one the union models", () => {
    const known = new Set([
      "Vehicles",
      "Emplacements",
      "Tripods",
      "Aircraft_Parts",
      "Structures",
      "Multitier_structures",
    ]);
    const seen = new Set(Object.values(targets).map((t) => t.ObjectType));
    expect([...seen].every((ot) => known.has(ot))).toBe(true);
    expect(seen.size).toBe(known.size);
  });

  it("narrows a Vehicles entry to VehicleLikeFields (Disable Level readable)", () => {
    // Looked up by ObjectType, not by name literal: several Targets.json keys
    // contain mismatched mojibake quote characters (a pre-existing data
    // encoding quirk, confirmed while generating the Python fixtures) that
    // don't survive round-tripping through a source file literal.
    const entry = Object.values(targets).find((t) => t.ObjectType === "Vehicles");
    expect(entry?.ObjectType).toBe("Vehicles");
    if (entry?.ObjectType === "Vehicles") {
      expect(typeof entry["Disable Level"]).toBe("string");
    }
  });

  it("narrows a Structures entry to RepairCost/DecayStartHours fields", () => {
    const entry = targets["Border base"];
    expect(entry?.ObjectType).toBe("Structures");
    if (entry?.ObjectType === "Structures") {
      expect(typeof entry.RepairCost).toBe("string");
      expect(typeof entry.DecayStartHours).toBe("string");
    }
  });

  it("narrows a Multitier_structures entry to Bmat cost/RepairCost fields", () => {
    const entry = targets["Safe House"];
    expect(entry?.ObjectType).toBe("Multitier_structures");
    if (entry?.ObjectType === "Multitier_structures") {
      expect(typeof entry["Bmat cost"]).toBe("string");
    }
  });

  it("weapon entries have the fields the impact-fuse check reads", () => {
    const rpg = weapons["RPG"];
    expect(rpg?.ObjectType).toBe("Weapons");
    expect(rpg?.["Dev Name"]).toBe("RpgAmmo");
    expect(typeof rpg?.Damage).toBe("string");
  });
});
