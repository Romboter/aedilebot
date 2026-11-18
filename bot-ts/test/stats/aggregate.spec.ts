import { describe, expect, it } from "vitest";
import { aggregate } from "../../src/stats/aggregate.js";
import type { RunRecord } from "../../src/stats/recorder.js";

const NOW = new Date("2026-11-18T12:00:00.000Z");
const r = (over: Partial<RunRecord> = {}): RunRecord => ({
  at: "2026-11-18T01:00:00.000Z", command: "kill", guildId: "1", options: {}, outcome: "ok", ms: 1, user: "u1", ...over,
});

describe("aggregate", () => {
  it("counts totals, per command and unique users", () => {
    const a = aggregate([r(), r({ user: "u2" }), r({ command: "how", user: "u1" })], NOW);
    expect(a.total).toBe(3);
    expect(a.perCommand).toEqual({ kill: 2, how: 1 });
    expect(a.uniqueUsers).toBe(2);
  });

  it("top weapons and targets: 5 entries, descending, from weapon/weapon1/weapon2 and target/entity", () => {
    const runs = [
      ...Array.from({ length: 3 }, () => r({ options: { weapon: "A", target: "T1" } })),
      r({ options: { weapon1: "A", weapon2: "B", target: "T2" } }),
      r({ command: "statsheet", options: { entity: "T1" } }),
      ...["C", "D", "E", "F"].map((w) => r({ options: { weapon: w } })),
    ];
    const a = aggregate(runs, NOW);
    expect(a.topWeapons[0]).toEqual(["A", 4]);
    expect(a.topWeapons).toHaveLength(5);
    expect(a.topTargets[0]).toEqual(["T1", 4]);
  });

  it("groups failed lookups by 'weapon / target'", () => {
    const miss = r({ outcome: "not_found", options: { weapon: "mamon", target: "zzzz" } });
    const a = aggregate([miss, miss, r({ outcome: "ok", options: { weapon: "ok" } })], NOW);
    expect(a.failedLookups).toEqual([["mamon / zzzz", 2]]);
  });

  it("errorsPerDay is the last 7 UTC days, oldest first, zero-filled, errors only", () => {
    const a = aggregate([
      r({ outcome: "error", at: "2026-11-18T00:30:00.000Z" }),
      r({ outcome: "error", at: "2026-11-12T23:59:00.000Z" }),
      r({ outcome: "error", at: "2026-11-11T12:00:00.000Z" }),
      r({ outcome: "not_found", at: "2026-11-17T12:00:00.000Z" }),
    ], NOW);
    expect(a.errorsPerDay.map(([d]) => d)).toEqual([
      "2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16", "2026-11-17", "2026-11-18",
    ]);
    expect(a.errorsPerDay.map(([, n]) => n)).toEqual([1, 0, 0, 0, 0, 0, 1]);
  });

  it("lastSwap is the newest admin_swap run with ok or error, rollback from options", () => {
    const a = aggregate([
      r({ command: "admin_swap", outcome: "ok", at: "2026-11-17T00:00:00.000Z", options: { target: "data" } }),
      r({ command: "admin_swap", outcome: "denied", at: "2026-11-18T09:00:00.000Z", options: { target: "data" } }),
      r({ command: "admin_swap", outcome: "ok", at: "2026-11-18T08:00:00.000Z", options: { target: "data", rollback: true } }),
    ], NOW);
    expect(a.lastSwap).toEqual({ at: "2026-11-18T08:00:00.000Z", outcome: "ok", rollback: true });
  });

  it("empty input gives zeros, empty lists and null", () => {
    const a = aggregate([], NOW);
    expect(a).toMatchObject({ total: 0, perCommand: {}, uniqueUsers: 0, topWeapons: [], topTargets: [], failedLookups: [], lastSwap: null });
    expect(a.errorsPerDay).toHaveLength(7);
  });

  it("errorsByType counts error outcomes by errorType, descending, unknown when missing", () => {
    const a = aggregate([
      r({ outcome: "error", errorType: "Exception" }),
      r({ outcome: "error", errorType: "Exception" }),
      r({ outcome: "error", errorType: "SwapFailed" }),
      r({ outcome: "error" }),
      r({ outcome: "not_found", errorType: "TargetNotFoundError" }),
    ], NOW);
    expect(a.errorsByType).toEqual([["Exception", 2], ["SwapFailed", 1], ["unknown", 1]]);
  });
});
