import { describe, expect, it } from "vitest";
import dataStorePlugin from "../../src/data/dataStore.js";

// PluginHost.swap() dynamically imports a real file:// URL at runtime, which
// only works against plain JS (see test/plugins/pluginHost.spec.ts's .mjs
// fixtures — that's what proves the swap mechanism itself). This file
// instead statically imports the real dataStore module (as vitest's own
// transform pipeline handles TS) to verify it's a well-formed
// PluginModule<DataSnapshot> that a PluginHost could safely swap in.
describe("data/dataStore (PluginModule<DataSnapshot> shape)", () => {
  it("api is a real, non-empty DataSnapshot", () => {
    expect(Object.keys(dataStorePlugin.api.weapons).length).toBeGreaterThan(0);
    expect(Object.keys(dataStorePlugin.api.targets).length).toBeGreaterThan(0);
    expect(dataStorePlugin.api.locations.size).toBeGreaterThan(0);
  });

  it("validate() does not throw against the real loaded snapshot", () => {
    expect(() => dataStorePlugin.validate?.()).not.toThrow();
  });

  it("has a version string", () => {
    expect(typeof dataStorePlugin.version).toBe("string");
    expect(dataStorePlugin.version.length).toBeGreaterThan(0);
  });
});
