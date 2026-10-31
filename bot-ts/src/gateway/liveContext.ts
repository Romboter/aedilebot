// The running bot process's live hot-swap state (Phase 3, goal C):
// constructs the three PluginHosts (data, calculator, fuzzy) and provides
// currentCalculatorContext(), which every gateway entry point (commandRouter,
// messageListener) calls fresh per incoming event to build a CalculatorContext
// from whatever is CURRENTLY swapped in — satisfying the plan's "read get()
// fresh per invocation, never cache across an await" atomicity rule for all
// three hosts at once, in one place, rather than scattered per call site.
import { fileURLToPath } from "node:url";
import { PluginHost } from "../plugins/pluginHost.js";
import type { DataSnapshot } from "../data/loader.js";
import dataPlugin from "../data/dataStore.js";
import type { CalculatorApi } from "../domain/calculator/plugin.js";
import calculatorPlugin from "../domain/calculator/plugin.js";
import type { CalculatorContext } from "../domain/calculator/handlers.js";
import type { FuzzyApi } from "../domain/fuzzy/plugin.js";
import fuzzyPlugin from "../domain/fuzzy/plugin.js";

export type SwapTarget = "data" | "calculator" | "fuzzy";

export interface LiveHosts {
  dataHost: PluginHost<DataSnapshot>;
  calculatorHost: PluginHost<CalculatorApi>;
  fuzzyHost: PluginHost<FuzzyApi>;
  /** The path each host was constructed from — also what a swap with no
   * explicit path defaults to (i.e. "reload the latest build of the same
   * module"), see commands/adminSwap.ts. */
  defaultPaths: Record<SwapTarget, string>;
}

function resolveBuiltPath(relativeToThisFile: string): string {
  return fileURLToPath(new URL(relativeToThisFile, import.meta.url));
}

export function createLiveHosts(): LiveHosts {
  const defaultPaths: Record<SwapTarget, string> = {
    data: resolveBuiltPath("../data/dataStore.js"),
    calculator: resolveBuiltPath("../domain/calculator/plugin.js"),
    fuzzy: resolveBuiltPath("../domain/fuzzy/plugin.js"),
  };
  return {
    dataHost: new PluginHost(dataPlugin, defaultPaths.data),
    calculatorHost: new PluginHost(calculatorPlugin, defaultPaths.calculator, 5, "isolated-dist"),
    fuzzyHost: new PluginHost(fuzzyPlugin, defaultPaths.fuzzy, 5, "isolated-dist"),
    defaultPaths,
  };
}

export function hostFor(hosts: LiveHosts, target: SwapTarget): PluginHost<unknown> {
  switch (target) {
    case "data":
      return hosts.dataHost;
    case "calculator":
      return hosts.calculatorHost;
    case "fuzzy":
      return hosts.fuzzyHost;
  }
}

export function currentCalculatorContext(hosts: LiveHosts): CalculatorContext {
  return hosts.calculatorHost.get().buildCalculatorContext(hosts.dataHost.get(), hosts.fuzzyHost.get());
}
