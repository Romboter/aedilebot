# Documentation maintenance standard

Audience: another maintainer who has no memory of this conversation, could be on-call at 03:00, and must not guess.

## Required runbook sections

Each runbook should have:
1. **Status and scope:** implemented, tested offline, planned, or requires production validation; applicable branch/OS.
2. **When to use it:** symptom, trigger or maintenance task.
3. **Prerequisites:** permission, safe maintenance window, backups and credentials (refer to names, never values).
4. **Procedure:** numbered commands, exact working directory, placeholders and safe guards.
5. **Verify success:** observable output and expected result.
6. **Rollback/recovery:** when to stop, what to revert, escalation.
7. **References:** exact repo files, related issues and further reading.

Prefer commands that can be pasted without modification except clearly identified placeholders; never invent service instance IDs, Steam usernames, server addresses, paths or GitHub secret values.

## Truthfulness and safety

- Separate **verified behavior** from **planned design** and **operator-owned steps**.
- If a step is not implemented, label it as a proposed procedure and link the blocker; do not write it like a working API.
- Do not document raw Steam asset uploads, public archive downloads, bypassing Discord authorization, or credential exposure.
- Preserve game-file export provenance. Describing processed CUE4Parse JSON as a lossless Unreal dump is incorrect until #40 passes.
- When an action might interrupt a running bot or delete data, begin with a check or backup. No unbounded rm -rf examples against production paths.
- All examples are non-secret and reasonably least privilege.
- Prefer Markdown portable to GitHub, Obsidian and VS Code: meaningful headings, links, tables only when clarifying.

## Change-control checklist

- [ ] Verify commands and file references against current code.
- [ ] Note changed branches, status and permissions.
- [ ] Add a verification and rollback path.
- [ ] Confirm no real secrets, private game assets or personal identifiers.
- [ ] Link new runbooks from docs/README.md; use relative links for local files.
- [ ] Run link/static validation, or explain any unavailable verification.
- [ ] If production behavior changed, update the runbook in the same PR.
- [ ] Require human approval for irreversible or production operations.

The old bot-ts/HANDOFF.md is historical, contains stale local paths and test counts, and is **not** the authoritative current-status page; use docs/STATUS.md until it is cleaned up in #32.
