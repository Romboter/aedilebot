# Runbook: Change game statistics or Locations.csv safely

**Status:** Manual edit + Node data reload is supported; automated admin review/approve **not implemented** (issues #13–#20). **Use for:** Foxhole game patch, wrong damage number, corrected relic/town alias.

## Protect the source of truth

The runtime loads data/Targets.json, Weapons.json, Damage.json, Bunker_piece.json and Locations.csv. Locations.csv is **headerless**, with three columns (hex name, location name, location type); known type names include Town Center TH, Post Office TH, School TH and Small/Medium/Large Relic. The loader creates a Map keyed **only by locationName**; duplicates overwrite earlier rows. No automatic per-hex disambiguation.

## Procedure

1. Identify the exact current branch/SHA and deployment data source. Compare authoritative patch notes, static exported map actor evidence and existing rows. **Do not** interpret a transient missing dynamic War API building as deletion of a permanent location (#13).
2. Make a dated, private backup of the exact four JSON files and Locations.csv; test their readability. Never change live data directly without an approved diff.
3. Edit in a review branch. Preserve JSON schema/type/aliases and line-based CSV structure. Check for duplicate or ambiguous names, unsupported location types, invalid punctuation/extra commas and BOM/CRLF implications.
4. Run:
   ~~~bash
   cd bot-ts
   npm ci
   npm run typecheck && npm test && npm run build
   ~~~
   From repo root check the expected data delta with git diff -- data/. For changed Python behavior, regenerate fixtures with pinned CI Python dependencies and review the diff; do not blindly regenerate away errors.
5. Obtain review, merge and deploy the **exact** data commit. If the Node process is active and trusted /admin_swap is configured, use target=data and verify that a known query resolves to the intended type and damage.
6. Record before/after results, approver, patch/source provenance, commit SHA and rollback procedure in the change record.

## Verification and rollback

Verify representative /kill and /statsheet queries using both old aliases and changed names. Incorrect result: roll back dataHost memory if available; restore previous data files **on disk** before controlled restart or another data reload. Remember dataHost rollback does not undo the disk edit. If ambiguous duplicates cannot be resolved, leave proposal unapproved.

**Do not use** /admin-data-poll/import/review/approve: those six commands are a Phase 4 design, not implemented. A raw export or automated nearest-name guess must be reviewed by a person.

**Sources:** [loader.ts](../../bot-ts/src/data/loader.ts), [Locations.csv](../../data/Locations.csv), [Phase 4 design](../superpowers/specs/2026-08-20-admin-data-pipeline-design.md).
