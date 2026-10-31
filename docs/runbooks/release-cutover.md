# Runbook: Release, production cutover, and reversal

**Status: PLANNED / NOT APPROVED.** The repository has no confirmed production Node service/container or completed Python-to-Node cutover. These are acceptance steps, **not** a claim that the deployment commands already exist. Applies to issue #26 and #27.

## Gate: before any production action

1. Confirm which service is really handling production Discord. Root Dockerfile/compose.yml currently run Python; bot-ts/main.ts logs into DEV_SERVER_TOKEN, not DEPLOYMENT_TOKEN. This is an explicit blocker: do not substitute a production token casually.
2. Complete and link evidence for side-by-side Python parity (#24), message intents (#23), secrets/log review (#25), container/AMP deployment and backup/rollback verification (#26), and a signed-off operator runbook.
3. Record an approved maintenance window, responsible operator, rollback owner, prior deployed commit SHA, current data version and Discord application identity.
4. Back up the actual service environment and data outside the repository; verify the backup can be read. Capture currently running image/tag or process unit.
5. Ensure only one active production bot instance uses the production token. Never let an unproven Node and Python deployment simultaneously race to handle the same Discord events.

## Proposed release sequence (execute only after implementation)

1. Build and test immutable Node artifact from a reviewed commit using CI; confirm exact SHA and artifact hash. Current Python GHCR releases do NOT satisfy this step.
2. Provision a **separate staging Node service** with development token and intended data files, without exposing a production token.
3. Exercise slash commands, invalid inputs, safe swap/rollback, startup/restart, log handling and the target AMP/container restart policy on staging.
4. Arrange single-writer cutover: stop/disable old production bot, start the approved Node service using a deliberately implemented production-token selection mechanism, synchronize intended commands, monitor user-facing responses.
5. Verify exact production application identity, key commands and autocomplete, error logs, recovery after restart and absence of duplicate replies.
6. Observe for the approved window; document validation and time of cutover.

## Immediate rollback (if error rate or incorrect answers occur)

1. Stop/disable Node **before** reactivating Python; ensure no overlapping production token sessions.
2. Restore the previous container/image/config and reviewed data files from the tested backup using your **actual deployment manager**, not hypothetical hardcoded commands.
3. Start previous Python service and verify bot identity, slash commands, sample answers, and log health.
4. Record reason for rollback; keep failing artifact/logs for investigation with secrets redacted.

## Hard stops

- Production token inadvertently used by development workflow.
- No tested rollback artifacts or backup.
- No documented restart policy/health check on the actual AMP host.
- Any of #23–#27 unresolved, or no explicit authorization for cutover.

**Sources:** [root Dockerfile](../../Dockerfile), [compose](../../compose.yml), [Node main](../../bot-ts/src/main.ts), [deployment issue](https://github.com/Romboter/aedilebot/issues/26), [cutover issue](https://github.com/Romboter/aedilebot/issues/27).
