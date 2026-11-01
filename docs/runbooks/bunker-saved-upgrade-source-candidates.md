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

The original `UpgradeStructureCodeName` tag is now **independently inspected** with the source-only CUE4Parse tag whitelist extended in pinned extractor commit `1fc0211706b1fd0351763ee33eb034caaea90550` (draft PR #91). The audit accepts original `TYPE` tags from only exact package-scoped, normalized `.uasset` sources, rejects duplicates and missing tags for saved fields, and records the actual original UE property type. This is **source declaration evidence**, not proof that the game executes a runtime upgrade. The independent original `CodeName` property and DataTable `FName` key proofs remain unchanged.

## Private validation

Private workflow branch `automation/bunker-upgrade-chain-source`; `.github/workflows/bunker-upgrade-source-audit.yml` reuses pinned Foxhole build `26058282`, `foxrunner`, exact PAK, CUE4Parse extractor, bounded original tag inspection, graph and benchmark. It runs synthetic tests and prints a bounded source-name/relationship summary, but **never raw original game numeric values**. Complete reports are created in temporary private scratch, cleaned with a shell trap; PAK identity checked before/after.

The status values are **not a published migration path**. In particular, multiple classes can save the same `CodeName`, and multiple reference types can share an identical numeric triplet. A compatible edge may therefore be entirely coincidental until independently corroborated.

## Pinned-run evidence

**Verified** in private runner [#41353595453](https://github.com/Romboter/foxhole-lab/actions/runs/41353595453), build `26058282`, graph digest `8a0a8b7c4fa26469b08ca8d39881a69d9beef06f17f520e6472ef8a1676a5a44`, **37 successful tests** (12 benchmark, 14 upgrade, 11 original-type identity).

- **507** type-proven saved class declarations against **506** distinct original structure row identities.
- **224** original saved `UpgradeStructureCodeName` UE property tags, **all 224 `NameProperty`**.
- **29** exact named target edges compatible with adjacent tiers of the same FoxBunker reference profile. These are **source-typed candidates**; several piece types share identical stats, so a compatible profile type is not necessarily the correct role.
- **178** additional original named upgrade targets that are not adjacent-tier steps in this narrow FoxBunker numeric crosswalk.
- **283** typed classes with no separately saved upgrade field, **16** `None` sentinels, **one** upgrade target absent from the original structure table.
- **137** classes explicitly serialize a `Tier` field, though the type/value semantics of that field were not promoted or assumed.
- Observed special case: `FortRadarT3` has a saved self-targeting upgrade name. Do not assume this is a game bug or reachable runtime upgrade.

No raw source numeric values, exported assets, production updates, or catalog modifications were published.

## Next evidence gap

With the original `UpgradeStructureCodeName` `NameProperty` tags now independently verified, next trace explicit upgrade chains together with saved `Tier`, parent `SuperStruct`, build/upgrade role, and actual model geometry to distinguish same-stat structures. The exact named target and its original tag are not proof that the engine uses that path. Inspect native upgrade semantics where available. Do not infer numerical data inheritance or auto-modify `data/` and `data_manual/` catalogs.
