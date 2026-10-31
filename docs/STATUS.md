# Implementation and operational status

**Scope:** Based on repository code in rewrite/node-ts and the separate, unmerged extraction draft PR #39. Recheck this table after any merge. This is a status record, not evidence of an active production service.

| Area | Status | Evidence / important limitation |
|---|---|---|
| Python bot | Existing implementation | Root Dockerfile and compose.yml run Python; production runtime has not been inspected |
| Node/TypeScript calculator and nine slash commands | Implemented, previously dev-bot-tested | bot-ts/src and GitHub CI; 193 tests recorded after #11; not evidence of current production deployment |
| Node free-text message listener | Coded but inactive | gateway/client.ts config uses intents: []; /how remains available |
| Node dev login | Implemented | bot-ts/src/main.ts requires DEV_SERVER_TOKEN; DEPLOYMENT_TOKEN is read but not used |
| Node release/container cutover | **Not implemented/verified** | Root Dockerfile remains Python-only; issues #23–#27 |
| Data/calculator/fuzzy hot-swap | Implemented and CI smoke-tested | PluginHost; calculator/fuzzy isolate compiled dist; data re-imports entry; real Discord command click-through not verified (#12) |
| Admin swap authorization | Implemented, deny-by-default | ADMIN_GUILD_ID + ADMIN_USER_IDS both required; command disabled by default in Discord integrations |
| Permanent Node CI | Implemented | .github/workflows/typescript-ci.yml: Node 22 tests/build and Python golden fixture drift |
| CI required branch checks | Workflow exists; enforcement unverified | Repo ruleset must require two checks (issue #31) |
| Static Town Base source decision | **Open blocker** | Dynamic War API is not authoritative for permanent map presence (#13) |
| SteamCMD acquisition on Ubuntu | **Draft and unverified with a licensed download** | PR #39 provides script; only source-level/CLI Linux exporter smoke tests passed |
| CUE4Parse Linux exporter build | Verified to compile/start | PR #39 offline GitHub Actions; no genuine Foxhole map export verified |
| Private archive of map JSON | Draft implementation | PR #39 uses SHA-256 manifests and Zstd; exact-byte tests, but no real game run or storage backup test |
| Full-fidelity raw Unreal actor/property JSON | **Not implemented** | Current upstream processed exporter can omit actors; issue #40 |
| Relic/Town detection/name/tier validation | Prototype only | Recoveries and issues #14–#17; old cross-map marker matching unreliable |
| Review/approve/update Locations.csv by Discord | Design only | Issues #18–#20 |
| Multi-host HA | Design only, unsafe draft | #30; supervised single host is sufficient starting point |
| Public Discord verification | Status unknown | #28–#29; do not equate eligibility with approval |

## Important branch distinctions

- **main** is the repository default branch and contains the Python bot.
- **rewrite/node-ts** contains implemented Node work and permanent CI.
- **feat/38-steamcmd-map-export** (draft PR #39) contains experimental SteamCMD, exporter, archival and offline validation code. Its scripts are not available in a clean checkout of rewrite/node-ts until merged.
- A docs branch does not deploy any service or establish new GitHub Actions runner registration.

## Hard release gates

Do not claim the rewrite is production-ready until: systematic Python parity acceptance (#24), message-intent policy (#23), production secrets and logs (#25), Node deployment/rollback on target host (#26), and explicit cutover acceptance (#27) are completed. Do not claim full map coverage until the exporter proves actor/property fidelity (#40).

Review the [roadmap](https://github.com/Romboter/aedilebot/issues/33) for dependencies and current issue states.
