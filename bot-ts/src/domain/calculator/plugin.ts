// domain/calculator's PluginHost<CalculatorApi> wrapper (Phase 3, goal C).
// The api is just handlers.ts's exports, bundled so a caller can do
// `calculatorHost.get().generalKillHandler(ctx, ...)` instead of a static
// import — the thing that actually makes a calculator-code swap observable.
//
// validate() needs a live DataSnapshot to smoke-test against (per the plan's
// risk #5: fixtures must be computed fresh at swap time, not hardcoded, or
// they go stale the moment a game patch changes the numbers they were
// "golden" against). Deliberately NOT threaded through PluginHost.swap() as
// an extra parameter (decided explicitly, not guessed): that would change
// the plan's own PluginModule/PluginHost interface. Instead validate() does
// its own `import("../../data/dataStore.js")` — always whatever that
// module's own on-disk snapshot is, independent of whether a separately-
// swapped data PluginHost currently has something else live. Acceptable
// since a calculator swap and a data swap are two different admin actions,
// not required to be transactional with each other.
import type { PluginModule } from "../../plugins/pluginHost.js";
import { EntityNotFoundError } from "../errors.js";
import {
  buildCalculatorContext,
  commandBunkerKillHandler,
  customKillHandler,
  easterEggCheck,
  generalBunkerKillHandler,
  generalDehuskHandler,
  generalDisableHandler,
  generalKillHandler,
  statsheetHandler,
} from "./handlers.js";

export interface CalculatorApi {
  buildCalculatorContext: typeof buildCalculatorContext;
  generalKillHandler: typeof generalKillHandler;
  customKillHandler: typeof customKillHandler;
  generalDisableHandler: typeof generalDisableHandler;
  generalDehuskHandler: typeof generalDehuskHandler;
  generalBunkerKillHandler: typeof generalBunkerKillHandler;
  commandBunkerKillHandler: typeof commandBunkerKillHandler;
  statsheetHandler: typeof statsheetHandler;
  easterEggCheck: typeof easterEggCheck;
}

function assertNonEmptyString(value: string, label: string): void {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`domain/calculator plugin validate: ${label} did not return a usable string`);
  }
}

async function validate(): Promise<void> {
  const dataModule = (await import("../../data/dataStore.js")) as {
    default: PluginModule<import("../../data/loader.js").DataSnapshot>;
  };
  const ctx = buildCalculatorContext(dataModule.default.api);

  // Smoke-tests a handful of representative operations against LIVE data —
  // deliberately NOT asserting exact output strings (those would go stale
  // the instant a game patch changes damage/health numbers; that's what the
  // build-time calculator-fixtures.json suite is for, before a swap is even
  // considered). This only confirms the swapped-in code can run each major
  // code path without throwing and produces a plausible reply.
  //
  // ponytail: "40mm"/"Border base"/"Power Plant Husk" are picked as
  // reasonably permanent Foxhole entities. If a future game patch renames or
  // removes one, this smoke test would need updating along with it — an
  // acceptable v1 limitation, not worth a self-healing "pick any entity from
  // the data" scheme for a smoke check.
  assertNonEmptyString(generalKillHandler(ctx, "40mm", "Border base"), "generalKillHandler");
  assertNonEmptyString(generalDisableHandler(ctx, "40mm", "40-250 “Alekto” Heavy Cannon"), "generalDisableHandler");
  assertNonEmptyString(generalDehuskHandler(ctx, "150mm", "Power Plant Husk"), "generalDehuskHandler");

  const statsheetResult = statsheetHandler(ctx, "40mm");
  if (statsheetResult instanceof EntityNotFoundError) {
    throw new Error("domain/calculator plugin validate: statsheetHandler could not find a known weapon (40mm)");
  }
}

const calculatorPlugin: PluginModule<CalculatorApi> = {
  version: new Date().toISOString(),
  validate,
  api: {
    buildCalculatorContext,
    generalKillHandler,
    customKillHandler,
    generalDisableHandler,
    generalDehuskHandler,
    generalBunkerKillHandler,
    commandBunkerKillHandler,
    statsheetHandler,
    easterEggCheck,
  },
};

export default calculatorPlugin;
