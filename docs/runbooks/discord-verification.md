# Runbook: Audit Discord verification, privileged intents and listing readiness

**Status:** Verification eligibility was documented historically, but **current approval status is unverified**. **Use for:** enabling Message Content, external guild expansion, app verification and public listing (#28–#29).

## Prerequisites

Application owner access to Discord Developer Portal, active privacy policy/terms URLs, support contact and a clear statement of exactly what messages and logs the deployed bot processes. Do not assume Python and Node have the same intent or logging policy.

## Procedure

1. Open the **actual application** in Discord Developer Portal and confirm its ID, verification state, installed guild count and application permissions. Record UTC screenshot/decision privately, avoiding token exposure.
2. Compare intended and actual gateway behavior:
   - Node gateway currently uses intents: [] and processes slash interactions only. Its message listener is wired but receives no messageCreate under that configuration.
   - Python bot has historically requested Message Content.
   - Decide whether user experience should be slash-only, mentions/DMs or guild message parsing. Do not enable a privileged intent merely to match old behavior.
3. Review privacy policy and terms under the **actual current deployment**: error_log.txt may record user queries; inspect retention, Discord IDs in admin audit logs, support contact and subprocessors.
4. Confirm current Discord platform rules for verification, App Directory, message intent access, permissions and review flow from official documentation.
5. Prepare truthful application listing descriptions, commands, screenshots, icons, support materials and policy URLs. Submit only when all requirements are met.
6. Test installation and command behavior in a controlled external guild (with owner permission), including command visibility and **global** admin_swap being unavailable to unrelated administrators.

## Verify / rollback

Verification success is an actual Developer Portal state, not an old “eligible” note. Record approval/rejection date and next action. If an intent causes login failures or policy violation, revert to minimal supported intents and slash commands, then correct permissions and resubmit as required. Do not publicly claim verified until approved.

**Sources:** [client config](../../bot-ts/src/gateway/client.ts), [privacy](../../privacypolicy), [terms](../../TnC), [verification issue #28](https://github.com/Romboter/aedilebot/issues/28), [listing issue #29](https://github.com/Romboter/aedilebot/issues/29).
