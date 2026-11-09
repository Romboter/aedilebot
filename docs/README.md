# AedileBot operations handbook

**Start here.** This is the canonical task-oriented handbook for maintainers of the Foxhole Discord damage calculator, the Node/TypeScript rewrite, and the proposed Foxhole map extraction pipeline.

## Choose the task you are performing

| Task | Procedure |
|---|---|
| Learn what is running and what remains unfinished | [Implementation status](STATUS.md) |
| Understand components and boundaries | [Architecture and data flow](architecture.md) |
| Set up an engineering workstation | [Developer setup](runbooks/developer-setup.md) |
| Register and test a development bot | [Discord development bot](runbooks/discord-dev-bot.md) |
| Investigate a failed build or fixtures | [CI and golden fixtures](runbooks/ci-fixtures.md) |
| Deploy or roll back a release | [Release and cutover](runbooks/release-cutover.md), [Service operations](runbooks/service-operations.md) |
| Make a reviewed data change | [Game data change](runbooks/data-change.md) |
| Check or regenerate weapon damage from an exported game build | [Weapon data generator](runbooks/weapon-generator.md) |
| Investigate asset-backed weapon/ammo references | [Trace weapon asset references](runbooks/weapon-asset-tracing.md) |
| Compare a licensed game build against existing statistics | [Read-only data audit](runbooks/game-data-audit.md) |
| Reload calculator, fuzzy logic or data in memory | [Hot swap and rollback](runbooks/hot-swap.md) |
| Handle a service outage or security event | [Incident response](runbooks/incident-response.md) |
| Set up a secure Foxhole extraction machine | [Ubuntu extraction host](runbooks/extraction-host.md) |
| Run SteamCMD and export maps | [Steam download and map export](runbooks/steam-map-export.md) |
| Run GitHub Actions on an isolated, private worker | [Private Actions runner](runbooks/private-actions-runner.md) |
| Extend C# to capture every raw actor/property | [Full-fidelity Unreal export](runbooks/full-fidelity-export.md) |
| Save, verify or restore historical maps | [Map archival and restoration](runbooks/map-archive-restore.md) |
| Diagnose missing relics or wrong locations | [Map extraction troubleshooting](runbooks/map-troubleshooting.md) |
| Protect or rotate credentials | [Credentials and permissions](runbooks/credentials.md) |
| Back up or restore service data | [Backup and restore](runbooks/backup-restore.md) |
| Check recurring operations | [Maintenance schedule](runbooks/maintenance.md) |
| Audit public Discord app readiness | [Discord verification](runbooks/discord-verification.md) |

## Essential operating rules

1. **Do not mistake design for deployment.** The Python Dockerfile/Compose are the existing implementation; Node is a rewrite with development-bot evidence but no confirmed production cutover. The full map archive/update workflow remains a **draft**, although a licensed Steam download and scoped extraction/comparison have now been verified on the separate private VM. See the [data audit](runbooks/game-data-audit.md).
2. **No unattended catalog edits.** Every proposed relic or town change needs data-source validation and an explicit approval path. Phase 4 review/approval code does not exist yet.
3. **Treat game files and map exports as private.** This GitHub repository is public. Never commit full PAKs, raw map JSON archives, bot tokens, Steam login state or identifiable logs.
4. **Do not attach credentialed persistent GitHub runners to this public repository.** Put execution in an isolated Ubuntu VM/container and a private dispatch repository.
5. **Back up before changing state; test restoration.** A Git commit is not a backup of SteamCMD authentication, production environment, or private archives.
6. **Confirm repository branch and SHA before running commands.** The default branch is Python main, while the Node work is on rewrite/node-ts; the old PR #39 runbooks predate the new CUE4Parse extractor and private-VM comparison work; verify current PRs before following an older draft.

## How these runbooks are written

Each task should state the current support status, prerequisites, exact steps, success criteria, failure/rollback path and references. Example paths are placeholders; do not assume the deployment actually lives under them. Commands target Ubuntu 24.04 unless labeled otherwise. Use least-privilege accounts; use sudo only where necessary to administer system-owned files.

**Maintenance:** When implementation changes, update its runbook in the same PR. [Documentation convention](CONTRIBUTING.md) defines review/validation expectations.

## Primary sources

- [Node rewrite](../bot-ts/) and [existing Python service](../src/).
- [Live Node configuration](../bot-ts/.env.example), [hot-swap design](../bot-ts/docs/hot-swap.md), [CI design](../bot-ts/docs/ci.md).
- [Phase 4 design spec](superpowers/specs/2026-08-20-admin-data-pipeline-design.md).
- [GitHub development roadmap](https://github.com/Romboter/aedilebot/issues/33) and [documentation tracker](https://github.com/Romboter/aedilebot/issues/32).
- [Map automation draft PR](https://github.com/Romboter/aedilebot/pull/39) and [full-fidelity map gap](https://github.com/Romboter/aedilebot/issues/40).
