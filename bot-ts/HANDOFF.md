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

Run from `bot-ts/`: `npm install && npm run typecheck && npm test` — currently **164 tests passing, 0 failures**.

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

## Status: Phase 2 (gateway/commands/discord.js wiring) is built, not yet live-tested

All of Phase 2's structural pieces are in place and typecheck/build/test clean, but **nothing has been run against a real Discord token yet** — there's no dev-server token available in this environment. Whoever has one needs to do the actual dev-server side-by-side validation the plan calls for before cutover.

Built:
- `domain/fuzzy/autocomplete.ts` — the O(n²) autocomplete fix (see below)
- `config/env.ts` — `DEPLOYMENT_TOKEN`/`DEV_SERVER_TOKEN`/`https_proxy` via Node's native `process.loadEnvFile()`, no dotenv dependency
- `gateway/errorPresenter.ts` — `handle_response_inner`'s except-chain → reply string + `error_log.txt` logging (logger is injectable, tests don't touch the filesystem)
- `gateway/client.ts`, `commandRouter.ts`, `commandSync.ts`, `command.ts` (shared `SlashCommand` interface), `messageListener.ts`
- `commands/{kill,disable,dehusk,customKill,bunkerKill,statsheet,help}.ts` + `autocompleteHandlers.ts` (shared autocomplete responders) + `index.ts`
- `main.ts` wired end-to-end (verified with a throwaway smoke script that builds the calculator context and constructs+wires the discord.js `Client` without calling `.login()` — this doesn't require a token and did work)

### The autocomplete O(n²) fix

Confirmed root cause reading `fuzzy.py`/`bot.py`: `kill_autocompletion_target` (and its weapon/disable/dehusk/statsheet siblings) did one O(n) scan to collect candidate alias **keys**, then for every one of those candidates re-ran a **full single-winner fuzzy match** just to resolve the key back to its canonical name — even though that key came straight out of the alias dictionary, so `dictionary.get(key)` gives the identical answer in O(1). That redundant per-candidate rescan was the O(n²), not the choice of fuzzy library.

User decided (asked directly, see conversation): reuse `fuzzball` (already a dependency, already used by `domain/fuzzy/match.ts`) instead of adding `fuzzysort` as the plan's "Fuzzy Matching Redesign" section literally names — the fix is eliminating the redundant rescan, which `fuzzball` already supports in one O(n) pass. No `tokenSetRatio.ts` was needed either, for the same reason.

One deliberate, documented behavior change from the Python original: the old rescan-per-candidate code incidentally handled a rare edge case (two different alias keys that are exact word-set permutations of each other) via its own internal tie-break; direct map lookup doesn't replicate that coincidence. Not worth an O(n²) to preserve — see the `ponytail:` comment in `autocomplete.ts`.

### Deliberate deviations from the Python original (all documented in-file)

- `statsheet.ts`: `statsheet_handler`'s Python caller has no not-found guard — indexing the returned `EntityNotFoundError` instance as `data[1]` would crash the interaction with no reply at all (Discord shows "This interaction failed"). Fixed to reply with the error message instead; not a parity requirement, a straightforward bug people would want fixed.
- `statsheet.ts`: the "Structures" embed branch's "Repair Cost" field is **preserved as buggy** — it reads `data[5]` (actually `DecayStartHours`) instead of `data[4]` (actual `RepairCost`), matching bot.py's live (mislabeled) output exactly. Commented in-file so it isn't "fixed" by accident later.
- `gateway/client.ts`: intents are the actual minimal set the code subscribes to (`Guilds`, `GuildMessages`, `MessageContent`) rather than blindly replicating Python's `Intents.default()` (which enables a bunch of non-privileged intents this bot never reads, like presences/bans/invites). `MessageContent` is still the only *privileged* intent, matching the existing memory note on this.
- `main.ts`: preserves bot.py's own inconsistency of reading both `DEPLOYMENT_TOKEN` and `DEV_SERVER_TOKEN` but only ever logging in with `DEV_SERVER_TOKEN` — not fixed here per the plan's explicit "resolve at cutover, not incidentally" guidance.

### Not yet done / still open

- **Live validation against a dev-server token** — nobody has run this against real Discord yet. This is the actual Phase 2 completion gate per the plan (side-by-side query comparison against the live Python bot).
- Slash command registration is guild-agnostic (`client.application.commands.set(...)`, i.e. global commands) — same as `bot.py`'s `client.tree.sync()` with no guild argument. Global command propagation can take up to an hour on Discord's side; if testing on a dev server, consider a guild-scoped sync for faster iteration (not built — flag if wanted).
- Phase 4 (admin data pipeline) hasn't been started — see the plan file for scope.

## Status: Phase 3 (hot-swap) is started — core mechanism done, not fully wired

Built:
- `plugins/pluginHost.ts` — the generic `PluginHost<T>` from the plan: `swap(path)` dynamically imports a module (cache-busted via a `?v=...` query string, since Node's ESM loader otherwise caches by resolved specifier and would silently keep serving a stale module after a rebuild), runs its `validate()`, and only on success does the atomic `this.current` reassignment. `rollback()` reverts to the most recent prior module via a bounded history (default 5). Any import/validate failure leaves `current` completely untouched.
- `test/plugins/pluginHost.spec.ts` (7 tests) — proves the actual atomicity claim the plan calls out as the primary risk, not just "swap() works": a broken module's `validate()` throwing leaves `current` untouched; an import of a nonexistent path leaves `current` untouched; bounded history evicts old rollback targets; and critically, **an in-flight call that read `get()` before a swap started keeps its old reference throughout the swap's pending `await`, and only calls to `get()` made *after* `swap()` resolves see the new module** — this is what "call sites read `get()` fresh, never cache across an await" actually buys you, demonstrated with a real dynamic import (not mocked) against `.mjs` fixture files in `test/fixtures/plugins/`.
- `data/dataStore.ts` — the first concrete `PluginModule<DataSnapshot>`: re-importing this file (through `PluginHost.swap()`) re-runs `loadDataSnapshot()` from disk, picking up whatever an admin data pipeline (Phase 4) wrote there since the process started. `validate()` does a cheap sanity check (non-empty weapons/targets) before letting a swap commit. Verified end-to-end with a throwaway smoke script: built it, swapped a real `PluginHost<DataSnapshot>` to the compiled `dist/data/dataStore.js`, confirmed the swap succeeds and the snapshot comes back intact.

### Not yet done / open design question

- **`domain/calculator` and `domain/fuzzy` are not yet wrapped in `PluginHost`.** The plan's `validate()` signature is `() => Promise<void> | void` — no parameters — but a meaningful validate for the calculator would need to replay `calculator-fixtures.json` against a **live** data snapshot (per the plan's own risk #5: fixtures must be computed fresh at swap time, not hardcoded, or they go stale after a game-data patch). Since `validate()` takes no arguments, the candidate module would have to reach for "the current data" some other way — e.g. importing `data/dataStore.ts` itself inside its own `validate()`. That's workable but has a real cross-plugin-dependency wrinkle worth deciding deliberately (does the calculator plugin's validate() import the *currently swapped-in* data host, or always the on-disk default?) rather than guessing an answer — flagging this for explicit direction before building it, not silently picking one.
- Nothing is wired into `main.ts`/`gateway/*` yet — `main.ts` still calls `loadDataSnapshot()`/the calculator handlers directly, not through a `PluginHost`. Matches the plan's own "purely additive, production behavior unchanged until first used" for this phase, but it does mean there's no admin-facing trigger command yet to actually invoke a swap in production.
- No admin trigger command/CLI (`scripts/admin-cli.ts`, or a Discord admin command) to call `.swap()` in a running process — everything above is invoked directly in tests/smoke scripts only.

## Workflow reminders for this session

- User wants to review/commit at each step — commit only when explicitly asked, with the `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer, one logical unit of work per commit.
- Run `npx tsc --noEmit` (typecheck) and `npx vitest run` (tests) from `bot-ts/` after every change, before reporting done.
- When porting a Python function, prefer generating fresh ground-truth fixtures via `venv/Scripts/python.exe -c "..."` (or extending `scripts/generate_fixtures.py`) over hand-deriving expected values — this methodology has caught 4 real behavioral divergences that would otherwise have shipped silently.
