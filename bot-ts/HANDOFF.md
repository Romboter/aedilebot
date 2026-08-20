# Rewrite Handoff — resume here

**Branch:** `rewrite/node-ts` (off `main` @ `90f4d16`)
**Plan file:** `C:\Users\Jason\.claude\plans\ok-i-have-more-iterative-ladybug.md` — read this first for full context (why Node/TS, hot-swap design, admin data pipeline, phasing, testing approach).

## What this is

Rewriting aedilebot (Python Discord damage-calculator bot for Foxhole) into Node/TypeScript, living at `bot-ts/` alongside the untouched Python `src/` (which keeps running in production throughout Phases 1–2). Three drivers: hot-swappable code/data modules ("bot never goes offline for updates"), an admin pipeline to update weapon/vehicle/location data after game patches, and — secondary — raw speed.

## Golden-fixture methodology (important — read before writing more code)

Every port in this branch is validated against **fixtures generated from the live Python code**, not hand-derived expected values. The generator is `scripts/generate_fixtures.py` (repo root) — rerun it any time with:

```
venv/Scripts/python.exe scripts/generate_fixtures.py
```

It writes to `test/fixtures/*.json` (repo root, shared — `bot-ts/test/fixtures.ts` loads from there, not a duplicate copy). Current fixture files:

- `calculator-fixtures.json` (24 cases) — consumed by `test/domain/calculator/handlers.spec.ts`
- `freetext-query-fixtures.json` (8 cases) — consumed by `test/domain/textParsing/freeTextQuery.spec.ts`
- `fuzzy-fixtures.json` (8 cases) — consumed by `test/domain/fuzzy/match.spec.ts`
- `alias-index-fixtures.json` — full dumps of all 5 Python alias dictionaries (2175 entries in the biggest one), consumed by `test/data/aliasIndex.spec.ts`
- `singularize-fixtures.json` (1531 words) — every distinct word in the real game data, consumed by `test/domain/singularize.spec.ts`
- `fuzzy-winner-fixtures.json` (60 cases) — programmatic typo queries with ground-truth winners, consumed by `test/domain/fuzzy/match.spec.ts`
- `fuzzy-scoring-fixtures.json` (300 pairs) — documents a known fuzzball/fuzzywuzzy raw-score divergence (see below), not asserted against directly

**venv setup note:** the repo's `venv/` was missing `inflect` despite it being in `requirements.txt` — already fixed by running `venv/Scripts/python.exe -m pip install "inflect>=7.0"` in an earlier session. If a fresh clone/environment hits `ModuleNotFoundError: No module named 'inflect'`, that's why.

## Status: Phase 1 (core engine) is done

Run from `bot-ts/`: `npm install && npm run typecheck && npm test` — currently **176 tests passing, 0 failures**.

All of `data/*`, `domain/errors.ts`, `domain/normalize.ts`, `domain/fuzzy/*`, `domain/textParsing/*`, and `domain/calculator/*` are ported and fixture-verified. Zero discord.js dependency anywhere in `domain/*`/`data/*`, per the plan.

### Commits on this branch (newest first)

1. Port `domain/textParsing/freeTextQuery.ts` (free-text regex dispatch) + `freetext-query-fixtures.json`
2. Port `domain/calculator/` (`bunkerMath.ts`, `multitier.ts`, `damageCalculator.ts`, `handlers.ts`) + `domain/textParsing/bunkerSpecParser.ts`
3. Fix `generate_fixtures.py` recording post-mutation bunker-spec input (deep-copy `args` before `run_case()`)
4. `84fc94e` — `src/domain/fuzzy/match.ts` (single-winner matchers)
5. `4a603d6` — `src/data/loader.ts` + `src/data/aliasIndex.ts`
6. `a2a65f1` — `src/domain/normalize.ts` + `src/domain/textParsing/moveStringToRear.ts`
7. `4ead206` — `src/data/schema.ts` (discriminated union on `ObjectType`)
8. `672468a` — `src/domain/errors.ts`
9. `84f0b1b` — Node/TS scaffold
10. `5e449c6` — `scripts/generate_fixtures.py` + initial fixtures

### Real bugs/divergences found and fixed during the port (don't reintroduce these)

- **`moveStringToRear`**: Python's `str.replace()` replaces every occurrence; JS's string-pattern `.replace()` only replaces the first. Fixed with `.replaceAll()`.
- **`singularize`**: Python's `inflect.singular_noun()` is more aggressive than the `pluralize` npm package — for unrecognized words (many proper nouns: "Daedalus", "class", "bus", "Icarus"...) inflect naively strips a trailing "s"; `pluralize` leaves them unchanged. Fixed with a fallback: try `pluralize.singular()` first, if unchanged and word ends in "s", strip it — verified exact match against all 1531 real words. One true exception found and hardcoded: `"gallows"` stays `"gallows"` (confirmed against live `inflect` output, not guessed) — see `INFLECT_INVARIANT_NOUNS` in `normalize.ts`.
- **`fuzzball` vs `fuzzywuzzy` scoring**: `fuzzball` (JS fuzzywuzzy port) diverges from Python's `fuzzywuzzy` by a few points on ~8% of (query, key) pairs — rounding/algorithm differences inside `partial_ratio`, not something worth patching a third-party lib for. Per the plan's own stated bar, `domain/fuzzy/match.ts` is validated on **which canonical name wins**, not exact scores (60 programmatic typo-query fixtures prove this holds).
- **Mojibake in `Targets.json`**: some keys (e.g. the "Alekto" vehicle) have mismatched left-curly-quote characters (`"` used on both sides instead of `"..."`) — a pre-existing data encoding quirk. Don't reference these names as source-file string literals in new tests; look them up by `ObjectType` or via a fixture instead.
- **`generate_fixtures.py` recording post-mutation input**: it recorded each fixture's `"input"` field *after* `run_case()` ran, but `command_bunker_kill_handler`/`general_bunker_kill_handler` mutate the `bunker_spec` dict in place (red/green estimation) — so the two `bunker_direct` cases with `green: -1, red: -1` were silently recording the *estimated* values as if that had been the original input. Fixed by deep-copying `args` before `run_case()` runs.

## Design notes for `domain/calculator/` and `domain/textParsing/`

- `handlers.ts` needs a `CalculatorContext` (built once via `buildCalculatorContext(loadDataSnapshot(dataDir))`) bundling the data snapshot + all 5 alias dictionaries + the location-name index — this is the thing Phase 3's `PluginHost`/hot-swap will eventually wrap.
- `statsheetHandler` returns `Array<string|number> | EntityNotFoundError` (not throwing on not-found) — same asymmetric-return quirk as the Python original; callers must check `instanceof EntityNotFoundError`.
- `multitierDamageCalculator`'s Python original has a dead `if self.damage_type == "BPDemolitionDamageType"` branch (always `False` since `damage_type` is never a bare string) — not replicated, documented in a comment in `multitier.ts`.
- `parseFreeTextQuery` (in `freeTextQuery.ts`) is a **pure parser only** — `{weapon, target, operation} | null`. It deliberately does NOT port `handle_response_inner`'s try/except-to-string conversion + `error_log.txt` file write — that's presentation/logging with I/O side effects, which belongs in `gateway/errorPresenter.ts` (Phase 2), not `domain/*`. Whoever wires up the gateway needs to: call `parseFreeTextQuery`, dispatch to the matching `domain/calculator/handlers.ts` function based on `operation` (`"bunker"` → `generalBunkerKillHandler`, others map 1:1), then catch domain errors and turn them into reply strings + log them, mirroring `handle_response_inner`'s except chain (see `src/bot.py` lines ~517-559 in the Python original for the exact message text expected per exception type).
- The "disable" free-text regex quirk is preserved as-is: it does NOT run `moveStringToRear` first, unlike "kill"/"dehusk" — matches `bot.py`'s inconsistency exactly, not fixed.

## Status: Phase 2 (gateway/commands/discord.js wiring) is built and LIVE-VALIDATED

Confirmed working against a real Discord dev bot (`bot-ts/.env` has a `DEV_SERVER_TOKEN` for a throwaway test application — **gitignored, do not commit it**, user said they'll rotate it eventually anyway). Run with `npx tsx src/main.ts` from `bot-ts/`. Observed live: successful login, guild connection ("Bot test server"), and global slash-command registration (`Synced 8 commands: help, kill, disable, dehusk, custom_kill, bunker_kill, statsheet, how`). User has manually exercised slash commands against it and confirmed it works.

Built:
- `domain/fuzzy/autocomplete.ts` — the O(n²) autocomplete fix (see below)
- `config/env.ts` — `DEPLOYMENT_TOKEN`/`DEV_SERVER_TOKEN`/`https_proxy` via Node's native `process.loadEnvFile()`, no dotenv dependency
- `gateway/errorPresenter.ts` — `handle_response_inner`'s except-chain → reply string + `error_log.txt` logging (logger is injectable; `error_log.txt` is now gitignored since real runs — including tests that exercise the real default logger — do write it)
- `gateway/client.ts`, `commandRouter.ts`, `commandSync.ts`, `command.ts` (shared `SlashCommand` interface), `messageListener.ts`
- `gateway/freeTextDispatch.ts` — shared by `messageListener.ts` and the `/how` command: dispatches a parsed free-text query to the right calculator handler + converts thrown domain errors to reply strings
- `commands/{kill,disable,dehusk,customKill,bunkerKill,statsheet,help,how}.ts` + `autocompleteHandlers.ts` (shared autocomplete responders) + `index.ts`
- **`/how` — new, not in the Python original.** User asked for a slash-command wrapper around the free-text prompt: `/how query:"many mammons to kill a ghouse"` behaves like typing `how many mammons to kill a ghouse` in chat (the command name supplies the implied "how"). Implemented by prepending `"how "` to the `query` option and running it through the exact same `parseFreeTextQuery` + `dispatchFreeTextQuery` on_message uses — same parser, same handlers, same error presentation, zero duplicated logic.
- `main.ts` wired end-to-end (verified with a throwaway smoke script that builds the calculator context and constructs+wires the discord.js `Client` without calling `.login()` — this doesn't require a token and did work)

### The autocomplete O(n²) fix

Confirmed root cause reading `fuzzy.py`/`bot.py`: `kill_autocompletion_target` (and its weapon/disable/dehusk/statsheet siblings) did one O(n) scan to collect candidate alias **keys**, then for every one of those candidates re-ran a **full single-winner fuzzy match** just to resolve the key back to its canonical name — even though that key came straight out of the alias dictionary, so `dictionary.get(key)` gives the identical answer in O(1). That redundant per-candidate rescan was the O(n²), not the choice of fuzzy library.

User decided (asked directly, see conversation): reuse `fuzzball` (already a dependency, already used by `domain/fuzzy/match.ts`) instead of adding `fuzzysort` as the plan's "Fuzzy Matching Redesign" section literally names — the fix is eliminating the redundant rescan, which `fuzzball` already supports in one O(n) pass. No `tokenSetRatio.ts` was needed either, for the same reason.

One deliberate, documented behavior change from the Python original: the old rescan-per-candidate code incidentally handled a rare edge case (two different alias keys that are exact word-set permutations of each other) via its own internal tie-break; direct map lookup doesn't replicate that coincidence. Not worth an O(n²) to preserve — see the `ponytail:` comment in `autocomplete.ts`.

### Deliberate deviations from the Python original (all documented in-file)

- `statsheet.ts`: `statsheet_handler`'s Python caller has no not-found guard — indexing the returned `EntityNotFoundError` instance as `data[1]` would crash the interaction with no reply at all (Discord shows "This interaction failed"). Fixed to reply with the error message instead; not a parity requirement, a straightforward bug people would want fixed.
- `statsheet.ts`: the "Structures" embed branch's "Repair Cost" field is **preserved as buggy** — it reads `data[5]` (actually `DecayStartHours`) instead of `data[4]` (actual `RepairCost`), matching bot.py's live (mislabeled) output exactly. Commented in-file so it isn't "fixed" by accident later.
- `gateway/client.ts`: intents are **currently `[]` (zero gateway intents), by explicit user request for dev-bot testing** — a deliberate step down from an earlier version of this file that requested `Guilds`/`GuildMessages`/`MessageContent` (the actual-use minimal set vs. Python's `Intents.default()`). Slash-command interactions work fine with zero intents (they're delivered regardless of `GatewayIntentBits`), but `readyClient.guilds.cache` stays empty and `messageCreate` never fires — `messageListener.ts`'s free-text "how many X to kill Y" chat parsing is wired but **currently inert**. To restore it: add back `GatewayIntentBits.Guilds`, `GuildMessages`, `MessageContent` in `createClient()` (`MessageContent` is privileged — also needs toggling on in the Discord Developer Portal's Bot settings for the application in use). Full reasoning is in the file's own header comment.
- `main.ts`: preserves bot.py's own inconsistency of reading both `DEPLOYMENT_TOKEN` and `DEV_SERVER_TOKEN` but only ever logging in with `DEV_SERVER_TOKEN` — not fixed here per the plan's explicit "resolve at cutover, not incidentally" guidance.
- **Guild-scoped command sync for fast dev iteration — new, not in the Python original.** `config/env.ts` gained `testGuildId` (`TEST_GUILD_ID` env var); when set, `commandSync.ts` registers commands to that one guild (near-instant propagation) instead of globally (up to an hour). `bot-ts/.env` currently has `TEST_GUILD_ID` set to the user's test server. Leave unset in production — global registration is what `bot.py`'s `client.tree.sync()` did.

### Not yet done / still open

- **Live login/connect/sync confirmed** (see above — including guild-scoped sync), but a full **side-by-side query comparison against the live Python bot** — the plan's actual Phase 2 cutover gate — hasn't been done yet. Manual spot-checking via `/how`/`/kill`/etc. has happened, not a systematic regression pass.
- `messageListener.ts` (free-text on_message parsing) is currently untestable live since gateway intents are zeroed out — see the client.ts note above for how to re-enable it when that's wanted.
- Phase 4 (admin data pipeline) hasn't been started — see the plan file for scope.

## Status: Phase 3 (hot-swap) is DONE and LIVE-VERIFIED

Built:
- `plugins/pluginHost.ts` — the generic `PluginHost<T>` from the plan: `swap(path)` dynamically imports a module (cache-busted via a `?v=...` query string, since Node's ESM loader otherwise caches by resolved specifier and would silently keep serving a stale module after a rebuild), runs its `validate()`, and only on success does the atomic `this.current` reassignment. `rollback()` reverts to the most recent prior module via a bounded history (default 5). Any import/validate failure leaves `current` completely untouched.
- `test/plugins/pluginHost.spec.ts` (7 tests) — proves the actual atomicity claim the plan calls out as the primary risk, not just "swap() works": a broken module's `validate()` throwing leaves `current` untouched; an import of a nonexistent path leaves `current` untouched; bounded history evicts old rollback targets; and critically, **an in-flight call that read `get()` before a swap started keeps its old reference throughout the swap's pending `await`, and only calls to `get()` made *after* `swap()` resolves see the new module** — this is what "call sites read `get()` fresh, never cache across an await" actually buys you, demonstrated with a real dynamic import (not mocked) against `.mjs` fixture files in `test/fixtures/plugins/`.
- `data/dataStore.ts` — the first concrete `PluginModule<DataSnapshot>`: re-importing this file (through `PluginHost.swap()`) re-runs `loadDataSnapshot()` from disk, picking up whatever an admin data pipeline (Phase 4) wrote there since the process started. `validate()` does a cheap sanity check (non-empty weapons/targets) before letting a swap commit. Verified end-to-end with a throwaway smoke script: built it, swapped a real `PluginHost<DataSnapshot>` to the compiled `dist/data/dataStore.js`, confirmed the swap succeeds and the snapshot comes back intact.

- `domain/calculator/plugin.ts` — the `PluginModule<CalculatorApi>` wrapper (`api` = all of `handlers.ts`'s exports bundled into one object, so a caller does `calculatorHost.get().generalKillHandler(ctx, ...)` instead of a static import — that's what actually makes a calculator-code swap observable). **Design question resolved with the user**: `validate()` does its own `import("../../data/dataStore.js")` rather than threading a data snapshot through `PluginHost.swap()` as an extra parameter — keeps `PluginHost<T>`'s interface exactly as the plan specifies, at the cost of always validating against `dataStore.ts`'s own on-disk snapshot rather than whatever a separately-swapped data `PluginHost` currently has live (acceptable: a calculator swap and a data swap are two different admin actions, not required to be transactional together).
- `validate()` deliberately does **not** replay all 24 `calculator-fixtures.json` cases or assert exact output strings — those would go stale the instant a game patch changes damage/health numbers, and that's what the build-time test suite is for anyway, before a swap candidate is even built. Instead it's a cheap smoke test: run `generalKillHandler`/`generalDisableHandler`/`generalDehuskHandler`/`statsheetHandler` against a few reasonably-permanent real entities ("40mm", "Border base", "Power Plant Husk", the Alekto tank) and confirm they don't throw and return non-empty strings. `ponytail:`-commented in-file as a known v1 limitation if those specific entities ever get renamed/removed by a patch.
- Verified end-to-end with a throwaway smoke script: built it, constructed a real `PluginHost<CalculatorApi>`, ran a kill query before and after a successful swap (same result, code path proven live), then attempted a swap to a nonexistent path and confirmed it was rejected (`ok: false`) with the working module completely untouched afterward.

### domain/fuzzy wrapped, and wired for real (this session, follow-up to the above)

- `domain/fuzzy/plugin.ts` — `PluginModule<FuzzyApi>` bundling `match.ts` + `autocomplete.ts`'s exports (grouped as one swappable unit, matching the plan's "domain/fuzzy/\*" listing). Same live-data smoke-test `validate()` pattern as the calculator plugin.
- **The DI change flagged as a follow-up decision was made**: `CalculatorContext` gained a `fuzzy: FuzzyApi` field (`buildCalculatorContext(data, fuzzy = defaultFuzzyApi)` — default keeps every existing call site working unchanged). `domain/calculator/handlers.ts`'s internal fuzzy calls (`resolveWeaponName`, `resolveTargetName`, `statsheetHandler`) now go through `ctx.fuzzy.*` instead of a static import — this is what makes a `domain/fuzzy` swap actually change calculator behavior. `commands/autocompleteHandlers.ts` was updated the same way, so autocomplete observes fuzzy swaps too. `easterEggCheck` deliberately stays on the static import (documented in-file: it runs before `ctx` exists and has no data dependency — not worth threading a ctx through for a whimsy feature).
- `test/domain/calculator/fuzzyInjection.spec.ts` proves this is a real seam, not a type-level no-op: swaps in a stub `FuzzyApi` and confirms `generalKillHandler`'s output changes accordingly.
- **`main.ts`/`gateway/*` are now wired to the real hosts.** `gateway/liveContext.ts` is new: constructs the three `PluginHost`s (`data`, `calculator`, `fuzzy`) once at startup and exposes `currentCalculatorContext(hosts)`, which `commandRouter.ts` and `messageListener.ts` now call **fresh per incoming interaction/message** (not once at startup) — this is what actually satisfies the plan's "read `get()` fresh per invocation" rule end-to-end, for all three hosts at once, rather than baking a `CalculatorContext` snapshot at boot and never refreshing it.
- **Admin trigger built**: `/admin_swap target:<data|calculator|fuzzy> path:<optional> rollback:<optional bool>` (new, not in the Python original). Gated by `setDefaultMemberPermissions(Administrator)` (Discord's own native command-permission system, not an in-code check). `path` defaults to the current build's own path per target (`hosts.defaultPaths`), so the common case is just `/admin_swap target:data` to reload after a rebuild. `SlashCommand.execute` gained a third `hosts: LiveHosts` parameter for this — every other command ignores it (structurally valid; a callback with fewer declared params still satisfies a wider function type).
- Verified end-to-end with a throwaway smoke script: swapped all three hosts live in sequence (data → calculator → fuzzy), confirmed a kill query gives the same result before/after, then proved a broken-path swap through the exact `hostFor()` helper `/admin_swap` uses is rejected without disruption, and rollback restores the prior version. Then ran the real bot (`npx tsx src/main.ts`) and confirmed `/admin_swap` registers alongside the other 8 commands (9 total now).

### Not yet done

- `/admin_swap` hasn't been exercised by a human clicking through Discord yet — only via the smoke script and command registration. Worth an actual manual click-test.
- No CLI equivalent (`scripts/admin-cli.ts`) — only the Discord command exists. The plan mentions "command/CLI" (either); a CLI would need its own IPC/signal mechanism to reach a *running* process's live `PluginHost`s (a separate CLI process can't call `.swap()` on another process's in-memory object directly) — not attempted, flagging as a real design gap if a CLI is wanted later, not silently deferred without a reason.

## Workflow reminders for this session

- User wants to review/commit at each step — commit only when explicitly asked, with the `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer, one logical unit of work per commit.
- Run `npx tsc --noEmit` (typecheck) and `npx vitest run` (tests) from `bot-ts/` after every change, before reporting done.
- When porting a Python function, prefer generating fresh ground-truth fixtures via `venv/Scripts/python.exe -c "..."` (or extending `scripts/generate_fixtures.py`) over hand-deriving expected values — this methodology has caught 4 real behavioral divergences that would otherwise have shipped silently.
