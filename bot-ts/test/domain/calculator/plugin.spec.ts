import { describe, expect, it } from "vitest";
import calculatorPlugin from "../../../src/domain/calculator/plugin.js";

// Static import (vitest transforms TS for this) — verifies the plugin is a
// well-formed PluginModule<CalculatorApi> a PluginHost could safely swap in.
// The actual dynamic-import swap mechanism itself is proven generically in
// test/plugins/pluginHost.spec.ts against plain .mjs fixtures.
describe("domain/calculator/plugin (PluginModule<CalculatorApi> shape)", () => {
  it("validate() succeeds against the real on-disk data snapshot", async () => {
    await expect(calculatorPlugin.validate?.()).resolves.toBeUndefined();
  });

  it("api exposes every calculator handler", () => {
    expect(typeof calculatorPlugin.api.buildCalculatorContext).toBe("function");
    expect(typeof calculatorPlugin.api.generalKillHandler).toBe("function");
    expect(typeof calculatorPlugin.api.customKillHandler).toBe("function");
    expect(typeof calculatorPlugin.api.generalDisableHandler).toBe("function");
    expect(typeof calculatorPlugin.api.generalDehuskHandler).toBe("function");
    expect(typeof calculatorPlugin.api.generalBunkerKillHandler).toBe("function");
    expect(typeof calculatorPlugin.api.commandBunkerKillHandler).toBe("function");
    expect(typeof calculatorPlugin.api.statsheetHandler).toBe("function");
    expect(typeof calculatorPlugin.api.easterEggCheck).toBe("function");
  });

  it("has a version string", () => {
    expect(typeof calculatorPlugin.version).toBe("string");
    expect(calculatorPlugin.version.length).toBeGreaterThan(0);
  });
});
