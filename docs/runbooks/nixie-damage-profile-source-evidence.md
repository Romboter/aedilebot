# DTDamageProfiles source audit (Nixie lead)

Reviewed: 2026-11-01. **Research only. No production catalog changes.**

## Evidence

- Foxhole Steam build: `26058282`, immutable read-only licensed PAK on the private `foxrunner`.
- Original extraction: exact `Data/DTDamageProfiles` and `Data/BPAmmoDynamicData`, plus the 34 `DamageTypes/` Blueprint packages.
- Code: `scripts/audit_nixie_damage_profile_sources.py` (this branch); `test/test_audit_nixie_damage_profile_sources.py`.
- External lead: `jimdcunningham/nixie-foxhole` commit `6255bfd302bfd2cffe4986fe9057a49213ca5951`, `tools/foxwatch/FoxWatchManifestAssetExtractor.cs` methods `LoadDamageProfilesByType`, `LoadAmmoDynamicDataRows`, `ExtractBunkerDestructionSharedData`.
- First private run [#41358269612](https://github.com/Romboter/foxhole-lab/actions/runs/41358269612) **failed before game export**: the exact-package manifest had invalid `.uasset` suffixes. Corrected by passing extensionless paths per `ExactBlueprintPackages.ReadManifest`.
- Passing private source audit [#41358358447](https://github.com/Romboter/foxhole-lab/actions/runs/41358358447). Follow-up naming/field-shape audit [#41358494079](https://github.com/Romboter/foxhole-lab/actions/runs/41358494079) checked additional bounded cases. Four synthetic tests passed, both table FName row-key types verified, original parser build succeeded. Raw exports and full report were temporary and removed.

## Verified result

The game ships `DTDamageProfiles` with **20 damage-profile rows and 20 target profile columns**. The human `data/Damage.json` has **19 matching row identifiers**. For those rows, all **342/342 shared numeric target-column values** match **the raw game table values directly** (330 direct-only matches and 12 values that happen to equal both their original and their 1-minus complement). There are **no** complement-only or mismatching shared values.

This is exact numeric agreement of the 19 matching damage-type rows and 18 shared target columns in the pinned game-source export. It is **not proof of runtime-effective mitigation or every damage mechanism**. In particular, Nixie's conversion `max(0, 1 - TierXStructure)` generates the corresponding damage factor from a mitigation fraction; it does **not** mean the original raw profile column stores that factor.

Other source coverage:
- `BPAmmoDynamicData` has 64 rows. **63/64** have saved `DamageType` references resolving to an exported `DamageTypes/` package; `UnexplodedOrdnance` does not have a resolvable saved reference in this audit.
- Original `UDataTable.RowMap` key type was verified as `FName` in both tables.
- Of 34 DamageType Blueprint packages, **32** have independently inspected saved `Type` original Unreal `EnumProperty` tags. `BPFlareDamageType` and `BPSmokeDamageType` lack a serialized local `Type` value; never assign an inherited value without separate proof.

## Specific gaps

| Gap | Current status |
|---|---|
| Game profile absent in human `Damage.json` | `AntiTankKineticStructure` |
| Human-only profile absent from current game table | `TankZombie` |
| Game target columns absent from human matrix | `Ice`, `WorldStructureHusk` |
| Saved ammo row without resolved damage-class package | `UnexplodedOrdnance` |
| DamageType class lacks locally serialized `Type` | `BPFlareDamageType`, `BPSmokeDamageType` |

These are **discrepancies to classify**, not automatically bugs. Do not delete human-only rows or change users' existing calculations until use/compatibility and actual gameplay semantics are reviewed.

## Relationship confidence, by stage

1. **Verified:** exact file/pinned-build identity, 20 profile rows, 20 columns, 342/342 numeric agreement for shared fields, two table FName keys; 32 saved original `Type: EnumProperty` tags.
2. **Saved-reference candidate:** 63 ammo rows contain a `DamageType` object reference pointing to an existing game damage-type package. A saved reference is not automatically the runtime-selected damage class.
3. **Not fully resolved:** saved class `Type` EnumProperty **value** -> exact `DTDamageProfiles` row key relation for all 34 packages. Inspect and reconcile the EnumProperty values; do not infer missing/inherited defaults.
4. **Not proven:** native `/Script/War` usage of `DTDamageProfiles` with target `ArmourType` / other mitigation classification, dynamic armor/subsystem modifiers, special effects, precision, overrides and alternate modes.

## Next experiment for Issue #81

- Record the original `Type` EnumProperty value and owning class/default export of each of the 32 saved tags, strictly normalize namespace prefixes only, and require a unique exact row candidate before promoting source linkage.
- Type-inspect the original nested `BPAmmoDynamicData.DamageType` DataTable row property (the current inspector verifies `FName` row keys, not individual row field tags) and compare saved object references against the class/enum identities.
- Resolve source `ArmourType`/mitigation categories across structures, vehicles, ships and aircraft and compare classifications to `data/Targets.json`. Explicitly classify the two extra game target columns and one unmatched damage profile.
- Keep the full game exports, per-row numbers, and provenance JSON in temporary private scratch only; print bounded counts and source identifiers. No Steam update, source PAK change, upstream pull, production catalog edit, or merge.

**Takeaway:** The legacy human mitigation matrix is source-reproducible from `DTDamageProfiles` for the 19 matching game rows and 18 shared fields. We have found the authoritative *source table for these stored values*, not a complete proof of the combat runtime.
