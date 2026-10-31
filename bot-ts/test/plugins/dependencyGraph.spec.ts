import { afterEach, describe, expect, it } from "vitest";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { PluginHost } from "../../src/plugins/pluginHost.js";

const tempRoots: string[] = [];

afterEach(async () => {
  // The running bot must keep staged files until shutdown. The test hosts
  // have finished here, so their entire throwaway repo can be removed.
  await Promise.all(tempRoots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

async function fixture() {
  const repoRoot = await mkdtemp(path.join(tmpdir(), "aedilebot-graph-"));
  tempRoots.push(repoRoot);
  const dist = path.join(repoRoot, "bot-ts", "dist");
  const feature = path.join(dist, "feature");
  await mkdir(feature, { recursive: true });
  await mkdir(path.join(dist, "data"), { recursive: true });
  await mkdir(path.join(repoRoot, "data"), { recursive: true });
  await writeFile(path.join(repoRoot, "data", "marker.json"), '{"ok":true}');
  const helper = path.join(feature, "helper.mjs");
  const entry = path.join(feature, "plugin.mjs");
  await writeFile(helper, 'export const label = "A";\n');
  await writeFile(
    path.join(dist, "data", "loader.mjs"),
    'import { fileURLToPath } from "node:url";\n' +
      'import path from "node:path";\n' +
      'export const dataDir = path.resolve(fileURLToPath(import.meta.url), "../../../../data");\n',
  );
  await writeFile(
    entry,
    'import { label } from "./helper.mjs";\n' +
      'import { dataDir } from "../data/loader.mjs";\n' +
      'export default { version: label, validate: () => {' +
      ' if (label === "BROKEN") throw new Error("bad plugin");' +
      '}, api: { label, dataDir } };\n',
  );
  return { repoRoot, helper, entry };
}

describe("PluginHost isolated-dist dependency graph", () => {
  it("reloads rebuilt transitive dependencies, isolates in-flight calls, and rolls back", async () => {
    const { repoRoot, helper, entry } = await fixture();
    const dataDir = path.join(repoRoot, "data");
    const host = new PluginHost({ version: "boot", api: { label: "boot", dataDir } }, entry, 5, "isolated-dist");

    expect((await host.swap(entry)).ok).toBe(true);
    expect(host.get()).toEqual({ label: "A", dataDir });
    const heldByInFlightCall = host.get();

    // Rebuild ONLY helper.mjs. The plugin wrapper is still byte-for-byte the
    // same file: a query-string cache-bust on that wrapper would miss this.
    await writeFile(helper, 'export const label = "B";\n');
    expect((await host.swap(entry)).ok).toBe(true);
    expect(host.get()).toEqual({ label: "B", dataDir });
    expect(heldByInFlightCall.label).toBe("A");
    expect(host.version).toBe("B");

    expect(host.rollback().ok).toBe(true);
    expect(host.get().label).toBe("A");
  });

  it("does not publish a rebuilt dependency that fails validation", async () => {
    const { helper, entry } = await fixture();
    const host = new PluginHost({ version: "boot", api: { label: "boot" } }, entry, 5, "isolated-dist");
    expect((await host.swap(entry)).ok).toBe(true);
    await writeFile(helper, 'export const label = "BROKEN";\n');
    const result = await host.swap(entry);
    expect(result.ok).toBe(false);
    expect(String(result.error)).toContain("bad plugin");
    expect(host.version).toBe("A");
    expect(host.get().label).toBe("A");
  });

  it("rejects paths outside compiled dist without affecting the current module", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aedilebot-not-dist-"));
    tempRoots.push(root);
    const entry = path.join(root, "plugin.mjs");
    await writeFile(entry, 'export default { version: "x", api: { label: "x" } };');
    const host = new PluginHost({ version: "boot", api: { label: "boot" } }, entry, 5, "isolated-dist");
    const result = await host.swap(entry);
    expect(result.ok).toBe(false);
    expect(String(result.error)).toContain("compiled module inside a dist/");
    expect(host.get().label).toBe("boot");
  });
});
