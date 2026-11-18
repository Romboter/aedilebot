// Append-only JSON Lines record of every slash-command run, plus the salt
// used to hash user IDs. A write failure is warned once and swallowed: stats
// must never break a command.
import { createHash, randomBytes } from "node:crypto";
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Outcome } from "./outcome.js";

export interface RunRecord {
  at: string;
  command: string;
  guildId: string | null;
  options: Record<string, string | number | boolean>;
  outcome: Outcome;
  errorType?: string;
  ms: number;
  /** Salted SHA-256 of the Discord user ID; the raw ID is never stored. */
  user: string;
}

export type RunInput = Omit<RunRecord, "user"> & { userId: string };

export function hashUserId(salt: string, userId: string): string {
  return createHash("sha256").update(`${salt}:${userId}`).digest("hex");
}

export function createRecorder(dir: string) {
  const file = path.join(dir, "commands.jsonl");
  const saltFile = path.join(dir, "salt");
  let warned = false;

  function salt(): string {
    mkdirSync(dir, { recursive: true });
    if (existsSync(saltFile)) {
      return readFileSync(saltFile, "utf8").trim();
    }
    const fresh = randomBytes(32).toString("hex");
    writeFileSync(saltFile, fresh, { mode: 0o600 });
    return fresh;
  }

  return {
    record(run: RunInput): void {
      try {
        const { userId, ...rest } = run;
        const line: RunRecord = { ...rest, user: hashUserId(salt(), userId) };
        appendFileSync(file, JSON.stringify(line) + "\n");
      } catch {
        if (!warned) {
          warned = true;
          console.warn("stats: could not write the command record; stats recording is degraded");
        }
      }
    },
    readAll(): RunRecord[] {
      let text: string;
      try {
        text = readFileSync(file, "utf8");
      } catch {
        return [];
      }
      const runs: RunRecord[] = [];
      for (const line of text.split("\n")) {
        if (line.trim() === "") continue;
        try {
          runs.push(JSON.parse(line) as RunRecord);
        } catch {
          // half-written or corrupt line: skip
        }
      }
      return runs;
    },
  };
}

export type Recorder = ReturnType<typeof createRecorder>;

let shared: Recorder | undefined;

/** STATS_DIR if set, else bot-ts/stats (two levels above dist/stats/ or src/stats/). */
export function defaultRecorder(): Recorder {
  shared ??= createRecorder(
    process.env.STATS_DIR?.trim() || path.resolve(fileURLToPath(import.meta.url), "../../../stats"),
  );
  return shared;
}
