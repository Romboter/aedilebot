import { describe, expect, it } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PluginHost } from "../../src/plugins/pluginHost.js";

const fixturesDir = path.resolve(fileURLToPath(import.meta.url), "../../fixtures/plugins");
function pluginPath(name: string): string {
  return path.join(fixturesDir, name);
}

function freshHost(historyLimit?: number) {
  return new PluginHost<{ label: string }>({ version: "initial", api: { label: "initial" } }, "initial", historyLimit);
}

describe("plugins/pluginHost", () => {
  it("swap() replaces the current api on success", async () => {
    const host = freshHost();
    const result = await host.swap(pluginPath("goodPluginA.mjs"));
    expect(result.ok).toBe(true);
    expect(host.get()).toEqual({ label: "A" });
    expect(host.version).toBe("A");
  });

  it("swap() leaves current untouched when validate() throws", async () => {
    const host = freshHost();
    const result = await host.swap(pluginPath("brokenPlugin.mjs"));
    expect(result.ok).toBe(false);
    expect(result.error).toBeInstanceOf(Error);
    expect(host.get()).toEqual({ label: "initial" });
  });

  it("swap() leaves current untouched when the import itself fails", async () => {
    const host = freshHost();
    const result = await host.swap(pluginPath("does-not-exist.mjs"));
    expect(result.ok).toBe(false);
    expect(host.get()).toEqual({ label: "initial" });
  });

  it("rollback() reverts to the previous module", async () => {
    const host = freshHost();
    await host.swap(pluginPath("goodPluginA.mjs"));
    await host.swap(pluginPath("goodPluginB.mjs"));
    expect(host.get()).toEqual({ label: "B" });

    const result = host.rollback();
    expect(result.ok).toBe(true);
    expect(host.get()).toEqual({ label: "A" });
  });

  it("rollback() with no history returns an error result and doesn't change current", () => {
    const host = freshHost();
    const result = host.rollback();
    expect(result.ok).toBe(false);
    expect(host.get()).toEqual({ label: "initial" });
  });

  it("history is bounded — old entries fall off once the limit is exceeded", async () => {
    const host = freshHost(1);
    await host.swap(pluginPath("goodPluginA.mjs")); // history: [initial]
    await host.swap(pluginPath("goodPluginB.mjs")); // history: [A]  ("initial" evicted, cap=1)

    expect(host.rollback().ok).toBe(true);
    expect(host.get()).toEqual({ label: "A" });
    expect(host.rollback().ok).toBe(false); // "initial" is gone
  });

  it("atomicity: an in-flight call started before a swap keeps using the old api while the swap is pending", async () => {
    const host = freshHost();

    // Simulates a call site that did the right thing: read get() once,
    // before the swap started, and is still "in flight" holding that value.
    const apiHeldByInFlightCall = host.get();

    const swapPromise = host.swap(pluginPath("slowPluginC.mjs")); // validate() takes 50ms
    // While the swap is pending, get() must still return the OLD api.
    expect(host.get()).toEqual({ label: "initial" });

    const result = await swapPromise;
    expect(result.ok).toBe(true);

    // Only after swap() resolves does get() see the new api...
    expect(host.get()).toEqual({ label: "C" });
    // ...while the reference the in-flight call already grabbed is
    // untouched, proving it finishes against the old module.
    expect(apiHeldByInFlightCall).toEqual({ label: "initial" });
  });
});
