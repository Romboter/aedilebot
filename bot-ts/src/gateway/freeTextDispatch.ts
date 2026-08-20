// Shared by messageListener.ts (on_message free-text) and commands/how.ts
// (the /how slash command, which is just the same free-text prompt wrapped
// in a command so it works without message-content-reading concerns) —
// dispatches a parsed free-text query to the matching calculator handler and
// converts any thrown domain error into its reply string.
import type { CalculatorContext } from "../domain/calculator/handlers.js";
import {
  generalBunkerKillHandler,
  generalDehuskHandler,
  generalDisableHandler,
  generalKillHandler,
} from "../domain/calculator/handlers.js";
import type { ParsedFreeTextQuery } from "../domain/textParsing/freeTextQuery.js";
import { runCalculatorOperation } from "./errorPresenter.js";

export function dispatchFreeTextQuery(ctx: CalculatorContext, parsed: ParsedFreeTextQuery, query: string): string {
  return runCalculatorOperation(() => {
    switch (parsed.operation) {
      case "kill":
        return generalKillHandler(ctx, parsed.weapon, parsed.target);
      case "disable":
        return generalDisableHandler(ctx, parsed.weapon, parsed.target);
      case "dehusk":
        return generalDehuskHandler(ctx, parsed.weapon, parsed.target);
      case "bunker":
        return generalBunkerKillHandler(ctx, parsed.weapon, parsed.target);
    }
  }, query);
}
