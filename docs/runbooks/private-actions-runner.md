# Runbook: Register and operate private GitHub Actions extraction runner

**Status: PROPOSED.** The private GitHub Actions automation repository and persistent authenticated runner are not confirmed provisioned. The reviewed workflow example exists only in draft PR #39. **Use for:** safely scheduling/dispatching Steam downloads or quarantining a compromised runner.

## Why a private runner

The AedileBot source repository is **public**. A persistent GitHub Actions runner holding a Steam session on a shared host is sensitive infrastructure. A malicious/unreviewed public pull request must not be allowed to execute arbitrary code on that host.

## Separation of duties

- **Public source repo:** C# extractor and tests, Node bot, offline CI on ephemeral GitHub-hosted runners; no game files or access to Steam credentials.
- **Private dispatch repo:** workflow entrypoint, allowed operators, approvals, pinned source revision. No untrusted pull_request execution on this runner.
- **Isolated Ubuntu VM:** private SteamCMD auth/session, persistent private archive directory, .NET runtime, Python packaging and runner registration. No production bot token, Docker host socket or unrelated application directories.

## Procedure

1. Provision isolated VM/container and dedicated non-root identity; review [extraction host](extraction-host.md) and use a **private** GitHub repository with restricted member access.
2. Audit the example workflow tools/map-extraction/private-runner-workflow.example.yml in PR #39. Copy it into the **private repo's** .github/workflows/ folder and replace REPLACE_WITH_REVIEWED_COMMIT_SHA with a reviewed immutable SHA from AedileBot. Do not check out a moving feature branch or unreviewed public PR content.
3. Register the GitHub runner under the private repo only, using GitHub's instructions. Give it the label foxhole-extract; set a private environment called foxhole-extraction with operator approvals and non-secret variables FOXHOLE_WORK_ROOT, FOXHOLE_STEAMCMD_PATH and FOXHOLE_STEAM_USER.
4. Locally complete Steam Guard login under the exact runner service user. Test a manual job only after resource capacity/entitlement verified. The workflow installs the pinned map-archival Python dependency and .NET SDK.
5. Dispatch manually at first. In Actions, inspect the current workflow SHA and run ID; review small inventory artifact and private local archive manifest. Do not publish map raw JSON or game PAK to public artifacts.
6. Schedule only after multiple unattended successful updates and validated relic/actor coverage. Schedules and workflow_dispatch require workflow code on the **private repo's default branch**.
7. Preserve job logs/metadata without exposing credentials, review access periodically, and monitor disk/backup.

## Compromise or decommission

Disable the runner in the private repo and isolate/stop the VM before investigating. Revoke any at-risk Steam sessions, GitHub registration tokens or secrets. Preserve private logs if required; do not destroy evidence. Remove registration before repurposing or deleting the VM; verify remaining workflows cannot run on it.

**Verify:** runs originate from private reviewed workflow, runner is isolated, game files never appear in GitHub artifacts, and only diagnostic report uploads succeed. If not, stop and follow [incident response](incident-response.md).

**Sources:** [draft PR #39](https://github.com/Romboter/aedilebot/pull/39), [Ubuntu provisioning](extraction-host.md), [credentials](credentials.md).
