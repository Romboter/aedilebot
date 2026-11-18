# `/admin_status` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record every slash-command run and add an operator-only `/admin_status` command that shows bot, game-data, usage and problem stats.

**Architecture:** The command router wraps every `command.execute` call, times it, captures the outcome through an `AsyncLocalStorage` that `presentError` and `adminSwap` write to, and appends one JSON line to `stats/commands.jsonl`. `/admin_status` reads that file, aggregates it with a pure function, and renders one ephemeral embed. No command file changes except `how`, `adminSwap`, and the new command.

**Tech Stack:** TypeScript, Node 22 (`node:fs`, `node:crypto`, `node:async_hooks`), discord.js 14, vitest. No new dependencies. Runs under Deno 2 on AMP, so no child processes (no `--allow-run`).

**Spec:** `docs/superpowers/specs/2026-11-18-admin-status-design.md`

## Global Constraints

- Operator-only: `ADMIN_USER_IDS` allowlist, user ID `237387841678606336`; `/admin_status` needs no `ADMIN_GUILD_ID`; `/admin_swap` keeps its user-plus-guild rule unchanged.
- Reply is ephemeral, one embed, at most 25 fields, at most 1024 characters per field value.
- Record per run: time, command, guild ID, options picked, outcome, response time, salted SHA-256 user hash. Never the raw user ID, token, or `/how` query text.
- A failed record write is logged and swallowed; it must never break a command.
- Storage: JSON Lines at `<STATS_DIR or bot-ts/stats>/commands.jsonl`, salt in `<dir>/salt`, directory gitignored, no pruning.
- `/admin_status` is not recorded; it is not listed in `/help`.
- No new dependencies; `domain/*` and `data/*` stay free of discord.js imports.
- Commit only when the user asks; never push.

## Review Focus

- Corrupt or half-written line in `commands.jsonl`: aggregation skips it, `/admin_status` still replies.
- Empty or missing record file: embed renders with zeros, no crash.
- `STATS_DIR` unwritable: commands still work, one logged warning, not one per run.
- A command that throws: the run is recorded as `error` and the original error still propagates.
- Embed value over 1024 characters (long top-N or guild lists): truncated, not rejected by Discord.
- `/how` with unparseable text: records `not_found`-style outcome without the raw text.

---

### Task 1: Outcome context

**Files:**
- Create: `bot-ts/src/stats/outcome.ts`
- Test: `bot-ts/test/stats/outcome.spec.ts`

**Interfaces:**
- Produces:
  - `type Outcome = "ok" | "not_found" | "error" | "denied"`
  - `markOutcome(outcome: Outcome, errorType?: string): void` (no-op outside `runWithOutcome`; first non-`ok` mark wins)
  - `runWithOutcome(fn: () => Promise<void>): Promise<{ outcome: Outcome; errorType?: string; thrown?: unknown }>`

- [ ] **Step 1: Write failing tests** in `outcome.spec.ts`: `markOutcome("not_found","TargetNotFoundError")` inside `runWithOutcome` returns that outcome and type; no mark returns `"ok"`; a throwing `fn` returns `outcome: "error"`, `errorType` = the error's `name`, and `thrown` set (does not rethrow); `markOutcome` outside any run does not throw; two concurrent runs do not see each other's marks.
- [ ] **Step 2: Run** `npx vitest run test/stats/outcome.spec.ts`. Expected: FAIL, module missing.
- [ ] **Step 3: Implement** with a module-level `AsyncLocalStorage<{outcome: Outcome; errorType?: string}>` from `node:async_hooks`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat(stats): outcome context`.

### Task 2: Outcome marks in `presentError` and `adminSwap`

**Files:**
- Modify: `bot-ts/src/gateway/errorPresenter.ts` (`presentError`), `bot-ts/src/commands/adminSwap.ts` (`execute`)
- Test: `bot-ts/test/gateway/errorPresenter.spec.ts`, `bot-ts/test/commands/adminSwap.spec.ts`

**Interfaces:**
- Consumes: `markOutcome` from Task 1.

- [ ] **Step 1: Add failing tests.** In `errorPresenter.spec.ts`, inside `runWithOutcome`: `TargetNotFoundError`, `WeaponNotFoundError`, `InvalidTypeError` and generic `EntityNotFoundError` → `not_found`; a plain `Error` → `error` with `errorType` `"Exception"`; `NoDamageError` → stays `ok`. In `adminSwap.spec.ts`: an unauthorized call → `denied`; a failed swap result → `error`; a successful swap → `ok`.
- [ ] **Step 2: Run** `npx vitest run test/gateway/errorPresenter.spec.ts test/commands/adminSwap.spec.ts`. Expected: new tests FAIL.
- [ ] **Step 3: Add `markOutcome` calls** in each `presentError` branch (mapping above, passing `error.name`) and in `adminSwap.execute` at the three exit points (`denied` for both denials, `error` for failed swap). Reply text and logging stay identical.
- [ ] **Step 4: Run** both specs plus `npm test`. Expected: all PASS.
- [ ] **Step 5: Commit** `feat(stats): mark outcomes from error presenter and admin_swap`.

### Task 3: Recorder, hashing and salt

**Files:**
- Create: `bot-ts/src/stats/recorder.ts`
- Modify: `.gitignore` (add `bot-ts/stats/`), `bot-ts/.env.example` (add `STATS_DIR=` with a comment)
- Test: `bot-ts/test/stats/recorder.spec.ts`

**Interfaces:**
- Consumes: `Outcome` from Task 1.
- Produces:
  - `interface RunRecord { at: string; command: string; guildId: string | null; options: Record<string, string | number | boolean>; outcome: Outcome; errorType?: string; ms: number; user: string }`
  - `createRecorder(dir: string): { record(run: Omit<RunRecord, "user"> & { userId: string }): void; readAll(): RunRecord[] }`
  - `defaultRecorder(): ReturnType<typeof createRecorder>` (lazy singleton; dir is `process.env.STATS_DIR` or `<bot-ts>/stats` resolved from `import.meta.url`)
  - `hashUserId(salt: string, userId: string): string` (hex SHA-256 of `salt + ":" + userId`)

- [ ] **Step 1: Write failing tests** in `recorder.spec.ts` using a temp dir: `record` then `readAll` round-trips one run; the stored line contains the hash and not the raw `userId`; the same user hashes identically across two `createRecorder` calls on the same dir (salt persisted) and differently under a different dir; `readAll` skips a corrupt line and a blank line; `readAll` on a missing file returns `[]`; with an unwritable dir (path under an existing file), `record` does not throw and warns once across several calls (spy on `console.warn`).
- [ ] **Step 2: Run** `npx vitest run test/stats/recorder.spec.ts`. Expected: FAIL.
- [ ] **Step 3: Implement.** Create the dir and salt lazily on first `record` (32 random bytes hex via `node:crypto`); append with `appendFileSync`; wrap the whole write in try/catch with a one-time `console.warn` that omits file contents.
- [ ] **Step 4: Run** the spec. Expected: PASS.
- [ ] **Step 5: Commit** `feat(stats): run recorder with salted user hash`.

### Task 4: Wire recording into the router

**Files:**
- Modify: `bot-ts/src/gateway/command.ts` (add optional `recordedOptions?(interaction: ChatInputCommandInteraction): Record<string, string | number | boolean>`), `bot-ts/src/gateway/commandRouter.ts`, `bot-ts/src/commands/how.ts`
- Test: `bot-ts/test/gateway/commandRouter.spec.ts` (new)

**Interfaces:**
- Consumes: `runWithOutcome` (Task 1), `defaultRecorder` / `createRecorder` (Task 3).
- Produces: `createCommandRouter(commands: SlashCommand[], recorder = defaultRecorder())`. Commands named `admin_status` are never recorded.

- [ ] **Step 1: Write failing tests** with fake interactions: a successful command records one run with the command name, guild ID, options from `interaction.options.data` (name→value), `ms` ≥ 0 and `outcome: "ok"`; a command that calls `markOutcome("not_found", ...)` records `not_found`; a command that throws records `error` and the router rethrows the same error; `admin_status` records nothing; a recorder whose `record` throws does not stop the command; `how` records `{weapon, target, operation}` from the parsed query and never the raw string, and an unparseable query records `{}` with no raw text.
- [ ] **Step 2: Run** `npx vitest run test/gateway/commandRouter.spec.ts`. Expected: FAIL.
- [ ] **Step 3: Implement.** In the chat-input branch, time with `performance.now()`, run `command.execute` inside `runWithOutcome`, record, then rethrow `thrown` if set. Options come from `command.recordedOptions?.(interaction)` else `interaction.options.data`. `how.recordedOptions` calls `parseFreeTextQuery` on `how <query>`.
- [ ] **Step 4: Run** the spec and `npm test`. Expected: all PASS.
- [ ] **Step 5: Commit** `feat(stats): record every slash-command run`.

### Task 5: Aggregation

**Files:**
- Create: `bot-ts/src/stats/aggregate.ts`
- Test: `bot-ts/test/stats/aggregate.spec.ts`

**Interfaces:**
- Consumes: `RunRecord` (Task 3).
- Produces: `aggregate(runs: RunRecord[], now: Date): Aggregate` where
  `Aggregate = { total: number; perCommand: Record<string, number>; uniqueUsers: number; topWeapons: [string, number][]; topTargets: [string, number][]; failedLookups: [string, number][]; errorsPerDay: [string, number][]; lastSwap: { at: string; outcome: Outcome; rollback: boolean } | null }`
  Top lists: 5 entries, descending. Weapons come from option names `weapon`, `weapon1`, `weapon2`; targets from `target`, `entity`. `failedLookups` counts `not_found` runs by their weapon/target option values joined as `weapon / target`. `errorsPerDay`: last 7 UTC days ending at `now`, oldest first, zero-filled, `outcome === "error"` only. `lastSwap`: newest `admin_swap` run with `outcome` `ok` or `error`.

- [ ] **Step 1: Write failing tests** with hand-built runs: totals and per-command counts; unique users by distinct `user`; top-5 cut and ordering; failed-lookup grouping; seven zero-filled days with errors on the right UTC day; `lastSwap` picks the newest and reports rollback from options; empty input gives zeros, empty lists and `null`.
- [ ] **Step 2: Run** `npx vitest run test/stats/aggregate.spec.ts`. Expected: FAIL.
- [ ] **Step 3: Implement** as one pure function with small Map-count helpers.
- [ ] **Step 4: Run** the spec. Expected: PASS.
- [ ] **Step 5: Commit** `feat(stats): aggregate command runs`.

### Task 6: `/admin_status` command

**Files:**
- Create: `bot-ts/src/commands/adminStatus.ts`, `bot-ts/src/stats/gitCommit.ts`, `bot-ts/src/gateway/operator.ts`
- Modify: `bot-ts/src/commands/index.ts` (add `adminStatus` to the array)
- Test: `bot-ts/test/commands/adminStatus.spec.ts`

**Interfaces:**
- Consumes: `aggregate` (Task 5), `defaultRecorder` (Task 3), `DataSnapshot` counts, `PluginHost.version`.
- Produces:
  - `isOperator(userId: string, env = process.env): boolean` (user in `ADMIN_USER_IDS`, snowflake-validated like `adminSwap`; no guild check)
  - `readGitCommit(startDir: string): string` (reads `.git/HEAD` and the ref file walking up from `startDir`; returns `"unknown"` on any failure; no child processes)
  - `buildStatusEmbed(input: { aggregate: Aggregate; guilds: { name: string; members: number }[]; startedAt: Date; now: Date; pingMs: number; commit: string; counts: { weapons: number; targets: number; vehicles: number }; versions: { data: string; calculator: string; fuzzy: string } }): EmbedBuilder`
  - `adminStatus: SlashCommand` named `admin_status`, `setDefaultMemberPermissions(0n)`, no options.

- [ ] **Step 1: Write failing tests.** `isOperator`: allowed, outsider, empty env, malformed ID. `readGitCommit`: a temp dir with `.git/HEAD` pointing at a ref gives the short hash; a detached HEAD gives the short hash; no `.git` gives `"unknown"`. `buildStatusEmbed`: has Bot, Game data, Usage and Problems fields; every field value ≤ 1024 characters and fields ≤ 25 even with 200 guilds and long names; zero data renders without throwing. `execute`: a non-operator gets an ephemeral refusal and no stats; the operator gets one ephemeral embed reply.
- [ ] **Step 2: Run** `npx vitest run test/commands/adminStatus.spec.ts`. Expected: FAIL.
- [ ] **Step 3: Implement.** `execute` checks `isOperator`, then builds the embed from `interaction.client.guilds.cache` (name and `memberCount`, largest first, top 5 shown), `interaction.client.uptime`, `interaction.client.ws.ping`, the live `DataSnapshot` via `hosts.dataHost.get()`, and vehicle count from `ctx.vehicleDictionary` size. Truncate list values with a trailing `…` at 1000 characters. Embed layout and wording are the builder's call.
- [ ] **Step 4: Run** the spec and `npm run typecheck && npm test`. Expected: all PASS.
- [ ] **Step 5: Commit** `feat: add operator-only /admin_status`.

### Task 7: Config, local run and AMP

**Files:**
- Modify: `bot-ts/.env` (local, gitignored), `docs/runbooks/credentials.md` (one line: `STATS_DIR`, `ADMIN_USER_IDS` now also gates `/admin_status`)

- [ ] **Step 1:** Add `ADMIN_USER_IDS=237387841678606336` and `ADMIN_GUILD_ID=1002992031506898954` to the local `bot-ts/.env`.
- [ ] **Step 2:** `npm run build && npm start`; in the test guild run `/kill`, a typo `/kill`, `/how` with junk, then `/admin_status`. Expected: embed shows the runs; `bot-ts/stats/commands.jsonl` has no raw user ID. Stop the bot.
- [ ] **Step 3:** After the user pushes `rewrite/node-ts`: add the same two lines to the AMP instance's `deno-server/app/bot-ts/.env`, click Update then Start, repeat the checks, confirm `stats/` survives a second Update.
- [ ] **Step 4: Commit** the runbook line only, when asked.

## Self-review notes

- Spec coverage: bot (guilds, uptime, ping, version, commit), game data (counts, live versions, last swap), usage (totals, per command, unique users, top weapons and targets), problems (failed lookups, errors per day), privacy, persistence, operator-only access, not-in-help: Tasks 1–7. The spec's "data version" is the plugin load time, since game data carries no version yet (see the stored memory about the help version line).
- Builder calls beyond the spec: fourth outcome `denied` (unauthorized `admin_swap`), kept so denials do not read as errors; `/admin_status` itself is excluded from records.
