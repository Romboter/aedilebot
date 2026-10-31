# Hot-swapping compiled ESM code safely

## Why a full graph snapshot is required

Node ESM caches modules by their resolved URL. Adding a query to the plugin entry point does not invalidate its static imports. A new calculator plugin wrapper can therefore continue executing older handlers or damage calculations.

The running bot supports two explicit strategies:

- **entry** (data only): re-import the data store entry with a changing URL. It re-reads the JSON and CSV in the repository data directory. Changes to loader JavaScript are not refreshed.
- **isolated-dist** (calculator and fuzzy): copy the entire compiled bot-ts/dist tree into a new sibling bot-ts/dist-hotswap-XXXXXX folder before importing the plugin. Every relative ESM dependency gets a new resolved URL, including deeper imports. This retains the same directory depth so data/loader still resolves the existing repository data directory.

A candidate is loaded and validated before it replaces the live module reference. Existing requests retain their old API object; rollbacks switch the reference to the previous validated version.

## Operator workflow

1. Build and test a full distribution with Node 22: cd bot-ts; npm ci; npm run build; npm test.
2. Run compiled JavaScript (npm start). Isolated code swaps require module paths inside the compiled dist directory. Using npx tsx src/main.ts is not supported for these code swaps.
3. Finish building before requesting a swap. Do not run a build simultaneously with snapshot copying: copying a partially overwritten dist tree is not an atomic deployment.
4. Use /admin_swap target:calculator or /admin_swap target:fuzzy for code changes. Use /admin_swap target:data to reload edited JSON/CSV content.
5. On failure the old module remains active. Use /admin_swap target:<area> rollback:true to restore the previous successful version. Different areas are **not** one coordinated transaction.

Do not modify or delete dist-hotswap-* directories while the bot process is running. In-flight calls, rollback or lazy dynamic imports may still require those files. Clean them up only after the process has stopped. A series of swaps consumes disk until that cleanup.

## Explicit limitations

- Runtime npm packages resolve from the same bot-ts/node_modules. Changes to external packages require a coordinated process restart.
- New code must remain compatible with the currently active data and other plugin APIs. Validation is a smoke test, not a full test suite or schema migration.
- Reloading code and reloading game data are separate operations, not an atomic pair.
- Rebuilding the original dist folder in place is not an atomic publish; a future production release process should build into immutable artifacts and switch to a published version.
- Untrusted plugins are executable code. **Issue #11 must restrict application operators and artifact paths** before this is safe in production.
- Issue #12 covers actual Discord click-through and rollback; issue #26 covers AMP/container deployment and cleanup procedures.
