# Runbook: Incident response — bot outage, bad data or compromised runner

**Status:** Operational procedure; not an assertion that monitoring, on-call paging or high availability are configured. **Use for:** Discord bot outage, corrupt answers, token exposure, suspicious admin swap, extraction-host compromise.

## First 10 minutes: determine severity and contain

1. Record time (UTC), impact, observer, bot/host identity, last known good commit and recent deployment/extraction jobs. Identify whether this is **dev** or **production** before touching anything.
2. For a **credential/security incident**, stop the impacted service/runner and revoke tokens/sessions using vendor controls. If the persistent extraction host is suspected compromised, **disable private runner registration and isolate the VM**; preserve forensic evidence. Do not run cleanup that destroys logs.
3. For **wrong answers/data**, stop new approvals and catalog edits; retain the last good data backup and game archive. If an in-memory swap caused the issue, invoke permitted rollback; restore files on disk too if they changed.
4. For **offline bot**, check the actual process supervisor, disk, memory, time, network, Discord service reachability and single-production-token ownership. Never reboot the entire host as the first response.

## Diagnostic matrix

| Signal | First investigation | Do not do |
|---|---|---|
| Missing Discord slash commands | Bot identity, TEST_GUILD_ID, command sync log, app installation | Blindly sync production globally |
| No free-text replies | Node intents: [] by design | Enable privileged intents without policy |
| Admin command denied | ADMIN_USER_IDS, ADMIN_GUILD_ID, Discord command visibility | Grant all guild admins global control |
| Wrong damage result after data edit | Git diff, data snapshot, previous answers and source provenance | Auto-apply raw live map diff |
| Error after hot-swap | PluginHost audit/error log, prior API version, disk snapshot | Delete dist-hotswap while live |
| Steam extraction suddenly empty | Steam Guard, Windows depot, PAK, CUE4Parse schema, lost actors | Treat zero relics as authoritative |
| Full archive/runner disk | df, old scratch, archive growth, approved offsite backup | Delete deduplicated archive blobs at random |

## Recovery and evidence

1. Take the smallest safe action to restore service: process restart under verified supervisor, code/data rollback, credential rotation, or halt extraction and preserve last successful manifest.
2. Verify user-facing command and representative known results. Confirm no duplicate production bot processes. For extraction, re-validate per-map hashes and raw fidelity before re-enabling scheduled runs.
3. Record exact change, incident timeline, affected users/servers if known, redacted logs, root cause, tested recovery and follow-up issue. Do not post sensitive logs to this public repository.

## Escalation / stop conditions

Pause deployment if production application identity is uncertain, backups cannot be restored, authorization scope is unclear, multiple instances may share a token, or proprietary exports might have leaked. No split-brain-safe HA system exists; issue #30 is design-only.

**Related:** [service operations](service-operations.md), [credentials](credentials.md), [release rollback](release-cutover.md), [archive restoration](map-archive-restore.md).
