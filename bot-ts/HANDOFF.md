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

- `calculator-fixtures.json` (24 cases) — **not yet consumed**, this is what the next task (domain/calculator) validates against
- `fuzzy-fixtures.json` (8 cases) — consumed by `test/domain/fuzzy/match.spec.ts`
- `alias-index-fixtures.json` — full dumps of all 5 Python alias dictionaries (2175 entries in the biggest one), consumed by `test/data/aliasIndex.spec.ts`
- `singularize-fixtures.json` (1531 words) — every distinct word in the real game data, consumed by `test/domain/singularize.spec.ts`
- `fuzzy-winner-fixtures.json` (60 cases) — programmatic typo queries with ground-truth winners, consumed by `test/domain/fuzzy/match.spec.ts`
- `fuzzy-scoring-fixtures.json` (300 pairs) — documents a known fuzzball/fuzzywuzzy raw-score divergence (see below), not asserted against directly

**venv setup note:** the repo's `venv/` was missing `inflect` despite it being in `requirements.txt` — already fixed by running `venv/Scripts/python.exe -m pip install "inflect>=7.0"` in this session. If a fresh clone/environment hits `ModuleNotFoundError: No module named 'inflect'`, that's why.

## Done so far (7 commits on this branch, all passing)

Run from `bot-ts/`: `npm install && npm run typecheck && npm test` — currently **103 tests passing, 0 failures**.

1. `5e449c6` — `scripts/generate_fixtures.py` + initial fixtures
2. `84f0b1b` — Node/TS scaffold (package.json, tsconfig, vitest, ESM)
3. `672468a` — `src/domain/errors.ts` (all exception classes, was scattered in `bot.py`)
4. `4ead206` — `src/data/schema.ts` (discriminated union on `ObjectType`, raw JSON field names preserved)
5. `a2a65f1` — `src/domain/normalize.ts` + `src/domain/textParsing/moveStringToRear.ts`
6. `4a603d6` — `src/data/loader.ts` + `src/data/aliasIndex.ts`
7. `84fc94e` — `src/domain/fuzzy/match.ts` (single-winner matchers)

### Real bugs/divergences found and fixed during the port (don't reintroduce these)

- **`moveStringToRear`**: Python's `str.replace()` replaces every occurrence; JS's string-pattern `.replace()` only replaces the first. Fixed with `.replaceAll()`.
- **`singularize`**: Python's `inflect.singular_noun()` is more aggressive than the `pluralize` npm package — for unrecognized words (many proper nouns: "Daedalus", "class", "bus", "Icarus"...) inflect naively strips a trailing "s"; `pluralize` leaves them unchanged. Fixed with a fallback: try `pluralize.singular()` first, if unchanged and word ends in "s", strip it — verified exact match against all 1531 real words. One true exception found and hardcoded: `"gallows"` stays `"gallows"` (confirmed against live `inflect` output, not guessed) — see `INFLECT_INVARIANT_NOUNS` in `normalize.ts`.
- **`fuzzball` vs `fuzzywuzzy` scoring**: `fuzzball` (JS fuzzywuzzy port) diverges from Python's `fuzzywuzzy` by a few points on ~8% of (query, key) pairs — rounding/algorithm differences inside `partial_ratio`, not something worth patching a third-party lib for. Per the plan's own stated bar, `domain/fuzzy/match.ts` is validated on **which canonical name wins**, not exact scores (60 programmatic typo-query fixtures prove this holds).
- **Mojibake in `Targets.json`**: some keys (e.g. the "Alekto" vehicle) have mismatched left-curly-quote characters (`“` used on both sides instead of `“...”`) — a pre-existing data encoding quirk. Don't reference these names as source-file string literals in new tests; look them up by `ObjectType` or via a fixture instead.

## Status: `domain/calculator/` is done (this session)

All 24 `calculator-fixtures.json` cases pass exactly (`test/domain/calculator/handlers.spec.ts`), plus 5 targeted unit tests for the trickiest bunker-math sub-functions (`bunkerMath.spec.ts`). 132 tests total, 0 failures, typecheck clean.

Files added: `src/domain/calculator/{bunkerMath,multitier,damageCalculator,handlers}.ts`, `src/domain/textParsing/bunkerSpecParser.ts`.

**Fixture-generator bug fixed along the way:** `scripts/generate_fixtures.py` recorded `"input"` in each fixture entry *after* `run_case()` ran, but `command_bunker_kill_handler`/`general_bunker_kill_handler` mutate the `bunker_spec` dict in place (red/green estimation) — so the two `bunker_direct` cases with `green: -1, red: -1` were silently recording the post-mutation values (`green: 22, red: 16` etc.) as if that had been the input all along. Fixed by deep-copying `args` before `run_case()` runs; fixtures regenerated. If you regenerate fixtures again in the future, this is already fixed — no action needed, just noting it in case old fixture JSON is lying around from before this fix.

**Design notes for whoever wires up Phase 2 (gateway):**
- `handlers.ts` needs a `CalculatorContext` (built once via `buildCalculatorContext(loadDataSnapshot(dataDir))`) — this is the thing Phase 3's `PluginHost`/hot-swap will eventually wrap.
- `statsheetHandler` returns `Array<string|number> | EntityNotFoundError` (not throwing on not-found) — same asymmetric-return quirk as the Python original; callers must check `instanceof EntityNotFoundError`.
- `domain/textParsing/freeTextQuery.ts` (port of `bot.handle_response`'s regex dispatch) is still **not built** — needed for `on_message` parity in Phase 2, but wasn't required for calculator fixture parity since `general_bunker_kill_handler` only needed `bunkerSpecParser.ts`.

## Original next-task notes (kept for context, now done above)

This is the big one — Python's `calculator.py` (487 lines), the `DamageCalculator` class + handler functions (`general_kill_handler`, `custom_kill_handler`, `general_disable_handler`, `general_dehusk_handler`, `general_bunker_kill_handler`, `command_bunker_kill_handler`, `statsheet_handler`, `easter_egg_check`). This is the primary Phase 1 parity gate per the plan — **all 24 `calculator-fixtures.json` cases must match exactly** before Phase 2 (Discord wiring) starts.

Everything it depends on already exists and is tested:
- `domain/errors.ts` — `NoDamageError` for the zero-damage `ZeroDivisionError` case, plus the `InvalidTypeError`/`TargetNotFoundError` family
- `domain/fuzzy/match.ts` — `fuzzyMatchTargetName`, `fuzzyMatchWeaponName`, `normalizedRatioEqual`/`normalizedPartialRatioEqual` (easter egg)
- `data/schema.ts` — `TargetEntry`/`WeaponEntry`/`DamageTable`/`BunkerPieceStats` types
- `data/loader.ts` — `loadDataSnapshot(defaultDataDir())` gives you `{targets, weapons, all, damages, bunkerStats, locations}`
- `data/aliasIndex.ts` — `getAllNames`, `getHuskNames`, `getVehicleNames`, `buildLocationNameIndex`/`isLocationName`

Read `src/calculator.py` (repo root, Python) carefully before porting — it has several non-obvious behaviors worth preserving exactly (or explicitly documenting if you choose not to):
- `multitier_damage_calculator`'s `if self.damage_type == "BPDemolitionDamageType"` branch is **dead code** — `self.damage_type` is always a dict, never a string, so this comparison is always `False`. Don't bother replicating the dead branch; just implement the always-taken 3-tier path. Document this in a comment so a future reader doesn't "fix" it into working code and change behavior.
- The impact-fuse low-roll adjustment applies only to a hardcoded `Dev Name` list (`ATRPGLightCAmmo`, `ATRPGAmmo`, `ATRPGIndirectAmmo`, `RpgAmmo`, `HELaunchedGrenade`, `ATLaunchedGrenadeW`, `ATGrenadeW`, `StickyBomb`, `MortarTankAmmo`, `HEGrenade`) — `kill_impact_fuse_range` fixture covers this (RPG weapon).
- Bunker math (`calculate_bunker_health`, `calculate_breachable_health`, `get_bunker_wet_multipler`, `calculate_bunker_repair`, `estimate_red_green`, `get_shelter_bonus`, `get_bunker_string`) is the most intricate/game-specific logic in the codebase — 3 direct-spec fixtures + 1 free-text-parser fixture cover it, but consider unit-testing the sub-functions in isolation too (per the plan's testing section) since they compose in ways an end-to-end fixture can silently under-cover.
- `get_bunker_spec`'s `tier_words` dict has multi-word keys like `"tier 3"` that can never match (input is whitespace-tokenized first) — only `"t1"/"t2"/"t3"/"concrete"` actually work. Already documented in `scripts/generate_fixtures.py`; the bunker free-text parser (`domain/textParsing/bunkerSpecParser.ts`, not yet built) needs to replicate this exact quirk, not silently fix it.
- `statsheet_handler` has a bare `except: return bot.EntityNotFoundError(entity_name)` — note it **returns** the exception instance rather than raising it in that one function; `generate_fixtures.py`'s `run_case` already handles this asymmetry (see the `isinstance(output, bot.EntityNotFoundError)` check) if you want to see how it was normalized for the fixture JSON.

Suggested file split (per the plan's layout): `bunkerMath.ts`, `multitier.ts`, `damageCalculator.ts` (the core class), `handlers.ts` (the module-level functions bot.py called). `domain/calculator` should have **zero** discord.js dependency, same as everything built so far.

## After that (remaining Phase 1 items, per the plan)

- `domain/textParsing/bunkerSpecParser.ts` (port of `parse.get_bunker_spec`) and `domain/textParsing/freeTextQuery.ts` (port of `bot.handle_response`'s regex dispatch) — needed for the `bunker_kill_freetext` fixture path and eventual `on_message` parity in Phase 2.
- Once `domain/calculator` is green against all 24 fixtures, Phase 1 is essentially done and Phase 2 (gateway/commands/discord.js wiring) can start — see the plan file's phase breakdown for what that involves.

## Workflow reminders for this session

- User wants to review/commit at each step — commit only when explicitly asked, with the `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer, one logical unit of work per commit.
- Run `npx tsc --noEmit` (typecheck) and `npx vitest run` (tests) from `bot-ts/` after every change, before reporting done.
- When porting a Python function, prefer generating fresh ground-truth fixtures via `venv/Scripts/python.exe -c "..."` (or extending `scripts/generate_fixtures.py`) over hand-deriving expected values — this methodology already caught 3 real behavioral divergences that would otherwise have shipped silently.
