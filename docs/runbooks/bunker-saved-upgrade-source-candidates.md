# Saved bunker upgrade CodeName edge candidates

**Research-only** follow-up to [FoxBunker's validated bunker benchmark](foxbunker-validated-bunker-row-benchmark.md) and [Issue #87](https://github.com/Romboter/aedilebot/issues/87).

## Question

The first pinned FoxBunker comparison found **51/51** tier profiles matching the original structure table's `StructuralIntegrity`, `MaxHealth`, and `RepairCost` values, with **20 unique** and **31 numerically ambiguous** type-proven class/row candidates. How can the ambiguous tiers be narrowed by source declarations **without** guessing identity from a filename or a matching number?

## Source audit

`scripts/audit_bunker_upgrade_source_candidates.py` accepts the **same pinned source graph**, original type-verified `CodeName` audit report and completed user-validated FoxBunker numeric benchmark report. It checks every covered saved structure class default against the source graph's exact package SHA-256.

For each original, independently typed `Default__*.CodeName` → `BPStructureDynamicData` FName row, it records:

1. Whether the class **explicitly serializes** `UpgradeStructureCodeName`. Absence is *not* evidence of no runtime upgrade.
2. Whether the saved upgrade token exactly identifies a row of the same original DataTable, not a similarly named guess.
3. Whether the source and destination candidate rows belong to **the same FoxBunker reference type at adjacent tiers** based on the earlier numeric benchmark. This is a **reference-compatible step candidate**, not a runtime-upgrade conclusion.
4. Whether the class explicitly saved `Tier` (presence, type/shape and fingerprint only), without claiming enum semantics or an inherited value.
5. Whether an explicit saved upgrade references a missing row, a `None` sentinel, a malformed field, or another valid row that has no reference-compatible tier step.

This deliberately **does not** assert the original UE property type for `UpgradeStructureCodeName` (not yet inspected in the original tag whitelist). Named FName lookups remain only original serialized *saved candidates* unless we independently inspect the original tag and runtime behavior. The proof of the *source* CodeName field and the DataTable row key remains unchanged from the previous auditor.

## Private validation

Private workflow branch `automation/bunker-upgrade-chain-source`; `.github/workflows/bunker-upgrade-source-audit.yml` reuses pinned Foxhole build `26058282`, `foxrunner`, exact PAK, CUE4Parse extractor, bounded original tag inspection, graph and benchmark. It runs synthetic tests and prints a bounded source-name/relationship summary, but **never raw original game numeric values**. Complete reports are created in temporary private scratch, cleaned with a shell trap; PAK identity checked before/after.

The status values are **not a published migration path**. In particular, multiple classes can save the same `CodeName`, and multiple reference types can share an identical numeric triplet. A compatible edge may therefore be entirely coincidental until independently corroborated.

## Next evidence gap

Extend the original UE tag inspector, in a separately reviewed and pinned extractor commit, to recognize `UpgradeStructureCodeName` and verify its actual original property type (expected `NameProperty` is a *hypothesis*, not yet asserted). Inspect explicit tier/upgrade targets and actual Blueprint `SuperStruct` relationships, plus native upgrade semantics if available. Do not infer numerical data inheritance or auto-modify `data/` and `data_manual/` catalogs.
