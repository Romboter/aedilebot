# Runbook: Hot-swap calculator, fuzzy logic or game data

**Status:** Implemented in Node rewrite; tested offline in CI; real Discord operator click-through remains #12. Code swaps require compiled Node 22. **Use for:** applying reviewed in-process code/data changes without restart.

## Prerequisites

- Reviewed/validated candidate, green Node CI, a backup and an operator who understands rollback.
- The running bot is the compiled Node process (npm start from bot-ts), not Python and not tsx.
- ADMIN_GUILD_ID and ADMIN_USER_IDS set to real permitted Discord snowflake IDs; the /admin_swap integration command explicitly permitted for trusted guild. Defaults deny everyone.
- Adequate free storage: calculator/fuzzy swaps copy the full compiled dist graph into a new dist-hotswap-* sibling.
- No active writes or compilation to dist while the snapshot is being copied; no changes to external npm dependencies.

## Procedure

1. Record currently deployed commit, source and data hashes; capture known-good /kill and /statsheet results. Back up the data directory before any edit.
2. Stage a full compatible build and run:
   ~~~bash
   cd bot-ts
   npm ci
   npm run typecheck && npm test && npm run build
   ~~~
   **Caution:** rebuilding live dist in place is not atomic. On production, use an approved immutable release deployment process (not yet implemented, #26) rather than building over a running tree.
3. In authorized Discord guild invoke /admin_swap with target data, calculator or fuzzy. For pure CSV/JSON edits, use target=data to reload file content.
4. Confirm private success reply and audit line containing actor, guild, action, target, outcome, version. Re-run known queries and compare. Failed swap should leave previous module active.
5. If a successful swap produces wrong results, invoke /admin_swap with same target and rollback=true. Test results again.

## What rollback does NOT do

Rollback changes the **in-memory plugin reference**, not the changed files on disk. Before a restart you must restore the reviewed disk version separately. Rollback is per plugin only; it is not a coordinated data+code transaction. Failed validation can still leave edited data files in place. Runtime external dependencies from node_modules are not hot-swapped.

Never remove dist-hotswap-* directories while the process is live. They may still be needed by in-flight or lazy imports, even after rollback. Clean only after process shutdown and backup review.

## Troubleshooting

- **Not authorized:** check both allowlist env vars, user/guild identity and Discord command visibility. Do not broaden permission to all guild administrators.
- **Failed code swap:** verify compiled dist path, Node 22, complete graph, disk space and type/shape compatibility; review private server error output.
- **Wrong answers after data swap:** roll back memory, restore prior JSON/CSV on disk and re-load/controlled restart after validation.
- **No rollback available:** history is empty; use approved service release rollback and backup.

**Sources:** [PluginHost](../../bot-ts/src/plugins/pluginHost.ts), [adminSwap.ts](../../bot-ts/src/commands/adminSwap.ts), [existing hot swap notes](../../bot-ts/docs/hot-swap.md), [issue #12](https://github.com/Romboter/aedilebot/issues/12).
