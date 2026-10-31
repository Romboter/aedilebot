# Runbook: Operating cadence and housekeeping

**Status:** Recommended schedule; no scheduled job, alert channel or on-call rotation is configured by this document. **Use for:** recurring maintenance, quarterly readiness review.

| Cadence | Operator checks | Evidence / failure response |
|---|---|---|
| Before each merge | Latest head SHA, both Node CI and Python fixture jobs green, security-sensitive diff and docs updated | Stop merge if red/stale or required status enforcement absent |
| After any release | Expected Discord bot identity, 9 slash commands, sample known and invalid inputs, logs, rollback path | Follow release/cutover or incident runbook |
| Daily when service operates | Service supervisor, duplicate bot process, errors, disk/memory, blocked permissions | Log actions; do not restart whole AMP host |
| On each Foxhole update | Steam update outcome, PAK fingerprint, map count, archived run manifest, known relic coverage | Reject partial export or missing actors; preserve old archive |
| Weekly | Archive growth, logs, failed CI, out-of-date pending issues, backup copies | Adjust capacity; never prune content-addressed blobs without reference analysis |
| Monthly | Restore a historical archived map and verify SHA, restore a data backup in staging, review failed swap audit events | Record restore evidence |
| Quarterly | Audit Discord app verification/intent/privacy status, Steam account access, GitHub private runner permissions, branch rulesets | Rotate/revoke unnecessary access; update runbooks |
| At project milestone | Reassess #13 static-source decision, #40 raw fidelity, release gates and long-term data archiving | Only change status with code/tests evidence |

## Housekeeping rules

- Never delete dist-hotswap-* while a Node process is running. Once process stopped, confirm copies are no longer referenced, then clean reviewed stale versions.
- Do not automatically clean archive/blobs: older manifests can reference unchanged content by hash. Long-term retention is currently indefinite by design; establish storage monitoring and backup, not silent pruning.
- Avoid repeated full game downloads where persistent SteamCMD installation can be updated incrementally; validate SteamCMD session and game version each job.
- Backlog status is not operational evidence. Link production deployment tests, issue and CI runs to status changes.

## Closeout

For each recurring check, record UTC time, host/service/branch, findings, action, verification and next scheduled review in the private operations log. A “green” test run does not prove the game export is complete or that Discord verification is approved.

**References:** [status ledger](../STATUS.md), [roadmap](https://github.com/Romboter/aedilebot/issues/33), [backup runbook](backup-restore.md).
