import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { createRecorder, hashUserId } from "../../src/stats/recorder.js";

const USER = "237387841678606336";
const run = (over: object = {}) => ({
  at: "2026-11-18T00:00:00.000Z", command: "kill", guildId: "1", options: { weapon: "a" },
  outcome: "ok" as const, ms: 5, userId: USER, ...over,
});

let dir: string;
beforeEach(() => { dir = mkdtempSync(path.join(tmpdir(), "stats-")); });
afterEach(() => { rmSync(dir, { recursive: true, force: true }); vi.restoreAllMocks(); });

describe("recorder", () => {
  it("round-trips a run and stores the hash, never the raw user id", () => {
    const r = createRecorder(dir);
    r.record(run());
    const [got] = r.readAll();
    expect(got?.command).toBe("kill");
    expect(got?.user).toMatch(/^[0-9a-f]{64}$/);
    expect(readFileSync(path.join(dir, "commands.jsonl"), "utf8")).not.toContain(USER);
    expect(got).not.toHaveProperty("userId");
  });

  it("hashes the same user identically across recorders on one dir, differently across dirs", () => {
    createRecorder(dir).record(run());
    createRecorder(dir).record(run());
    const [a, b] = createRecorder(dir).readAll();
    expect(a?.user).toBe(b?.user);
    const other = mkdtempSync(path.join(tmpdir(), "stats-"));
    try {
      createRecorder(other).record(run());
      expect(createRecorder(other).readAll()[0]?.user).not.toBe(a?.user);
    } finally {
      rmSync(other, { recursive: true, force: true });
    }
  });

  it("readAll skips corrupt and blank lines", () => {
    const r = createRecorder(dir);
    r.record(run());
    writeFileSync(path.join(dir, "commands.jsonl"), readFileSync(path.join(dir, "commands.jsonl"), "utf8") + "\n{not json\n");
    r.record(run({ command: "how" }));
    expect(r.readAll().map((x) => x.command)).toEqual(["kill", "how"]);
  });

  it("readAll on a missing file returns []", () => {
    expect(createRecorder(path.join(dir, "nope")).readAll()).toEqual([]);
  });

  it("an unwritable dir does not throw and warns once", () => {
    const blocker = path.join(dir, "file");
    writeFileSync(blocker, "x");
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const r = createRecorder(path.join(blocker, "sub"));
    expect(() => { r.record(run()); r.record(run()); r.record(run()); }).not.toThrow();
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it("hashUserId is salt-dependent hex sha256", () => {
    expect(hashUserId("s1", "u")).toMatch(/^[0-9a-f]{64}$/);
    expect(hashUserId("s1", "u")).not.toBe(hashUserId("s2", "u"));
  });
});
