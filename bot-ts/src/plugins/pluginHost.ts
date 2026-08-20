// Hot-swap mechanism (rewrite goal C — "the bot should never go offline for
// a data/logic update"). One PluginHost<T> instance per swappable area
// (domain/calculator, domain/fuzzy, data/dataStore, per the plan).
//
// Atomicity contract: `current` is only ever reassigned in the single
// synchronous statement at the end of swap(), after the candidate module has
// been imported AND validated. Every call site must read get() fresh per
// invocation, never cache the returned api object across an await boundary —
// that's what makes an in-flight call safe: it's already holding the old api
// reference and finishes against it, while anything calling get() after the
// swap lands sees the new one. JS's single-threaded run-to-completion
// semantics between awaits mean there's no torn/half-updated state to guard
// against; see test/plugins/pluginHost.spec.ts for the atomicity proof.
//
// This is NOT fault tolerance — pair with a process supervisor (e.g. Docker
// `restart: unless-stopped`) for actual crash recovery. Hot-swap only avoids
// *planned* downtime.
import { cp, mkdtemp, rm } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

export interface PluginModule<T> {
  version: string;
  validate?: () => Promise<void> | void;
  api: T;
}

export interface SwapResult {
  ok: boolean;
  error?: unknown;
}

interface HistoryEntry<T> {
  path: string;
  module: PluginModule<T>;
}

const DEFAULT_HISTORY_LIMIT = 5;

// "entry" reloads just the plugin wrapper, appropriate for data-only changes.
// "isolated-dist" snapshots the entire compiled dist tree to a unique sibling,
// giving every static relative ESM dependency a fresh resolved module URL.
export type PluginImportStrategy = "entry" | "isolated-dist";

async function stageIsolatedDist(entryPath: string): Promise<{ entryPath: string; stageRoot: string }> {
  const absolute = path.resolve(entryPath);
  let distRoot = path.dirname(absolute);
  while (path.basename(distRoot) !== "dist") {
    const parent = path.dirname(distRoot);
    if (parent === distRoot) {
      throw new Error("isolated-dist swaps require a compiled module inside a dist/ directory");
    }
    distRoot = parent;
  }

  const relativeEntry = path.relative(distRoot, absolute);
  // Sibling dist-hotswap-... preserves loader.ts ../../../../data path depth.
  const stageRoot = await mkdtemp(distRoot + "-hotswap-");
  try {
    // Staging the full tree also refreshes deeper transitive relative imports.
    await cp(distRoot, stageRoot, { recursive: true });
    return { entryPath: path.join(stageRoot, relativeEntry), stageRoot };
  } catch (error) {
    await rm(stageRoot, { recursive: true, force: true });
    throw error;
  }
}

export class PluginHost<T> {
  private current: PluginModule<T>;
  private currentPath: string;
  private readonly history: Array<HistoryEntry<T>> = [];
  private readonly historyLimit: number;
  private importCounter = 0;
  private readonly importStrategy: PluginImportStrategy;

  constructor(
    initial: PluginModule<T>,
    initialPath: string,
    historyLimit: number = DEFAULT_HISTORY_LIMIT,
    importStrategy: PluginImportStrategy = "entry",
  ) {
    this.current = initial;
    this.currentPath = initialPath;
    this.historyLimit = historyLimit;
    this.importStrategy = importStrategy;
  }

  /** Always read fresh — never hold this across an `await`, or an in-flight
   * call stops being isolated from a concurrent swap. */
  get(): T {
    return this.current.api;
  }

  get version(): string {
    return this.current.version;
  }

  /** Imports the module at `path` in isolation, runs its validate() (if
   * any), and only on success does the atomic reference reassignment. Any
   * failure — import error or validate() throwing/rejecting — leaves
   * `current` completely untouched. */
  async swap(path: string): Promise<SwapResult> {
    let candidate: PluginModule<T>;
    let stageRoot: string | undefined;
    try {
      let candidatePath = path;
      if (this.importStrategy === "isolated-dist") {
        const stage = await stageIsolatedDist(path);
        candidatePath = stage.entryPath;
        stageRoot = stage.stageRoot;
      }

      // A query reloads only the entry module; static dependencies stay
      // cached. The isolated strategy instead changes the whole URL graph.
      const url = pathToFileURL(candidatePath).href +
        (this.importStrategy === "entry" ? "?v=" + Date.now() + "-" + this.importCounter++ : "");
      const imported = (await import(url)) as { default: PluginModule<T> };
      candidate = imported.default;
      if (candidate.validate) {
        await candidate.validate();
      }
    } catch (error) {
      if (stageRoot !== undefined) {
        // Rejected release never became visible to callers.
        await rm(stageRoot, { recursive: true, force: true }).catch(() => undefined);
      }
      return { ok: false, error };
    }

    this.history.push({ path: this.currentPath, module: this.current });
    if (this.history.length > this.historyLimit) {
      this.history.shift();
    }
    this.current = candidate;
    this.currentPath = path;
    // Retain successful snapshots until process shutdown: in-flight code and
    // lazy imports may still depend on them, even after history eviction.
    return { ok: true };
  }

  /** Manual escape hatch for a swap that passed validate() but was later
   * found wrong in production — reverts to the most recent prior module,
   * bypassing validate() (rollback always goes to something that was
   * current before, so it was already validated when it was swapped in). */
  rollback(): SwapResult {
    const previous = this.history.pop();
    if (previous === undefined) {
      return { ok: false, error: new Error("no previous module to roll back to") };
    }
    this.current = previous.module;
    this.currentPath = previous.path;
    return { ok: true };
  }
}
