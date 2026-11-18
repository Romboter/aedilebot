// Pure aggregation of command-run records for /admin_status.
import type { Outcome } from "./outcome.js";
import type { RunRecord } from "./recorder.js";

export interface Aggregate {
  total: number;
  perCommand: Record<string, number>;
  uniqueUsers: number;
  topWeapons: [string, number][];
  topTargets: [string, number][];
  failedLookups: [string, number][];
  errorsPerDay: [string, number][];
  errorsByType: [string, number][];
  lastSwap: { at: string; outcome: Outcome; rollback: boolean } | null;
}

const TOP_N = 5;
const DAYS = 7;
const WEAPON_OPTIONS = ["weapon", "weapon1", "weapon2"];
const TARGET_OPTIONS = ["target", "entity"];

function bump(map: Map<string, number>, key: string): void {
  map.set(key, (map.get(key) ?? 0) + 1);
}

function top(map: Map<string, number>, n = TOP_N): [string, number][] {
  return [...map.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, n);
}

const str = (v: unknown): string | undefined => (typeof v === "string" && v !== "" ? v : undefined);

export function aggregate(runs: RunRecord[], now: Date): Aggregate {
  const perCommand: Record<string, number> = {};
  const users = new Set<string>();
  const weapons = new Map<string, number>();
  const targets = new Map<string, number>();
  const failed = new Map<string, number>();
  const errorDays = new Map<string, number>();
  const errorTypes = new Map<string, number>();
  let lastSwap: Aggregate["lastSwap"] = null;

  for (const run of runs) {
    perCommand[run.command] = (perCommand[run.command] ?? 0) + 1;
    users.add(run.user);
    for (const name of WEAPON_OPTIONS) {
      const w = str(run.options[name]);
      if (w) bump(weapons, w);
    }
    for (const name of TARGET_OPTIONS) {
      const t = str(run.options[name]);
      if (t) bump(targets, t);
    }
    if (run.outcome === "not_found") {
      const w = str(run.options.weapon) ?? str(run.options.weapon1);
      const t = str(run.options.target) ?? str(run.options.entity);
      const label = [w, t].filter(Boolean).join(" / ");
      if (label) bump(failed, label);
    }
    if (run.outcome === "error") {
      bump(errorDays, run.at.slice(0, 10));
      bump(errorTypes, run.errorType ?? "unknown");
    }
    if (run.command === "admin_swap" && (run.outcome === "ok" || run.outcome === "error")) {
      if (lastSwap === null || run.at > lastSwap.at) {
        lastSwap = { at: run.at, outcome: run.outcome, rollback: run.options.rollback === true };
      }
    }
  }

  const errorsPerDay: [string, number][] = [];
  for (let i = DAYS - 1; i >= 0; i--) {
    const day = new Date(now.getTime() - i * 86_400_000).toISOString().slice(0, 10);
    errorsPerDay.push([day, errorDays.get(day) ?? 0]);
  }

  return {
    total: runs.length,
    perCommand,
    uniqueUsers: users.size,
    topWeapons: top(weapons),
    topTargets: top(targets),
    failedLookups: top(failed),
    errorsPerDay,
    errorsByType: top(errorTypes, 10),
    lastSwap,
  };
}
