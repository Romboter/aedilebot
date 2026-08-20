import { describe, expect, it } from "vitest";
import fuzzyPlugin from "../../../src/domain/fuzzy/plugin.js";

// Static import (vitest transforms TS for this) — verifies the plugin is a
// well-formed PluginModule<FuzzyApi> a PluginHost could safely swap in. The
// dynamic-import swap mechanism itself is proven generically in
// test/plugins/pluginHost.spec.ts.
describe("domain/fuzzy/plugin (PluginModule<FuzzyApi> shape)", () => {
  it("validate() succeeds against the real on-disk data snapshot", async () => {
    await expect(fuzzyPlugin.validate?.()).resolves.toBeUndefined();
  });

  it("api exposes every fuzzy-matching function", () => {
    expect(typeof fuzzyPlugin.api.fuzzyMatchTargetName).toBe("function");
    expect(typeof fuzzyPlugin.api.fuzzyMatchWeaponName).toBe("function");
    expect(typeof fuzzyPlugin.api.fuzzyMatchAny).toBe("function");
    expect(typeof fuzzyPlugin.api.fuzzyPerfectMatchAny).toBe("function");
    expect(typeof fuzzyPlugin.api.normalizedRatioEqual).toBe("function");
    expect(typeof fuzzyPlugin.api.normalizedPartialRatioEqual).toBe("function");
    expect(typeof fuzzyPlugin.api.autocompleteCandidates).toBe("function");
  });

  it("has a version string", () => {
    expect(typeof fuzzyPlugin.version).toBe("string");
    expect(fuzzyPlugin.version.length).toBeGreaterThan(0);
  });
});
