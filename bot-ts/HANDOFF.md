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

Run from `bot-ts/`: `npm install && npm run typecheck && npm test` — currently **140 tests passing, 0 failures**.

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

## Next: Phase 2 (gateway/commands/discord.js wiring)

Phase 1 is complete — all core engine fixtures pass. Per the plan's phase breakdown, Phase 2 is:

- `gateway/client.ts` — discord.js `Client` singleton, intents, `on_ready`
- `gateway/commandSync.ts` — slash command registration (`/kill`, `/disable`, `/dehusk`, `/custom_kill`, `/bunker_kill`, `/statsheet`, `/help`)
- `gateway/commandRouter.ts` + `commands/*.ts` — one file per slash command, each calling into `domain/calculator/handlers.ts`
- `gateway/messageListener.ts` — `on_message` free-text handling via `domain/textParsing/freeTextQuery.ts`
- `gateway/errorPresenter.ts` — domain-error → user-facing string conversion + logging (see design note above)
- Autocomplete for `kill`/`disable`/`dehusk`/`custom_kill`'s target/weapon fields — note the O(n²) bug in the Python original (`bot.py`'s `kill_autocompletion_target` rescans on every alias/tie resolution) should NOT be reproduced; `domain/fuzzy/match.ts` was already redesigned to do one pass (see the plan's "Fuzzy Matching Redesign" section) — the autocomplete callback just needs to call it correctly (single pass, no follow-up rescans).

Validate against the dev server (separate Discord app/token) with a fixed regression query list compared to the Python bot's live output — this is the cutover gate per the plan.

## Workflow reminders for this session

- User wants to review/commit at each step — commit only when explicitly asked, with the `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer, one logical unit of work per commit.
- Run `npx tsc --noEmit` (typecheck) and `npx vitest run` (tests) from `bot-ts/` after every change, before reporting done.
- When porting a Python function, prefer generating fresh ground-truth fixtures via `venv/Scripts/python.exe -c "..."` (or extending `scripts/generate_fixtures.py`) over hand-deriving expected values — this methodology has caught 4 real behavioral divergences that would otherwise have shipped silently.
