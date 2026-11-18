// Per-command-run outcome, carried through AsyncLocalStorage so presentError
// and adminSwap can mark it without the router needing their return values.
import { AsyncLocalStorage } from "node:async_hooks";

export type Outcome = "ok" | "not_found" | "error" | "denied";

interface Store {
  outcome: Outcome;
  errorType?: string;
}

const storage = new AsyncLocalStorage<Store>();

/** No-op outside runWithOutcome. The first non-"ok" mark wins. */
export function markOutcome(outcome: Outcome, errorType?: string): void {
  const store = storage.getStore();
  if (store === undefined || store.outcome !== "ok") {
    return;
  }
  store.outcome = outcome;
  if (errorType !== undefined) {
    store.errorType = errorType;
  }
}

export async function runWithOutcome(
  fn: () => Promise<void>,
): Promise<{ outcome: Outcome; errorType?: string; thrown?: unknown }> {
  const store: Store = { outcome: "ok" };
  let thrown: unknown;
  let didThrow = false;
  try {
    await storage.run(store, fn);
  } catch (error) {
    didThrow = true;
    thrown = error;
    store.outcome = "error";
    store.errorType = error instanceof Error ? error.name : "Exception";
  }
  return {
    outcome: store.outcome,
    ...(store.errorType !== undefined ? { errorType: store.errorType } : {}),
    ...(didThrow ? { thrown } : {}),
  };
}
