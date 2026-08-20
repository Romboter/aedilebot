// The first concrete PluginHost<T> target (rewrite goal C, Phase 3): this
// module IS the swappable unit for data/*.json + Locations.csv. Re-importing
// it via PluginHost.swap() (which cache-busts the specifier) re-runs
// loadDataSnapshot() from disk at import time, picking up whatever the admin
// data pipeline (Phase 4, not yet built) has written there since the process
// started.
//
// Not yet wired into gateway/client.ts or commands/*.ts — those still call
// loadDataSnapshot() directly via main.ts. Swapping this in for production
// use is a separate, deliberate step (see HANDOFF.md), matching the plan's
// "purely additive, production behavior unchanged until first used".
import type { PluginModule } from "../plugins/pluginHost.js";
import type { DataSnapshot } from "./loader.js";
import { defaultDataDir, loadDataSnapshot } from "./loader.js";

const snapshot = loadDataSnapshot(defaultDataDir());

const dataStorePlugin: PluginModule<DataSnapshot> = {
  version: new Date().toISOString(),
  validate: () => {
    // Cheap sanity check, not a full fixture replay — this module has no
    // domain/calculator dependency to run one against (and shouldn't grow
    // one just for this; that belongs in domain/calculator's own plugin
    // wrapper). Just confirms the load produced something plausible before
    // PluginHost commits to it as the new current snapshot.
    if (Object.keys(snapshot.weapons).length === 0) {
      throw new Error("dataStore: loaded 0 weapons — refusing to swap in an empty/broken data snapshot");
    }
    if (Object.keys(snapshot.targets).length === 0) {
      throw new Error("dataStore: loaded 0 targets — refusing to swap in an empty/broken data snapshot");
    }
  },
  api: snapshot,
};

export default dataStorePlugin;
