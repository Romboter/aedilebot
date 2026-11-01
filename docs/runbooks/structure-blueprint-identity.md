# Runbook: Structure Blueprint identity and data sources

**Status:** Read-only research. Game build `26058282`; no generator,
production updates, scheduled checks, or automatic PR creation.

## The relationship to resolve

```text
Structures/BP... Blueprint
  BlueprintGeneratedClass.SuperStruct.ObjectPath → parent Blueprint, if exported
  Default__*.Properties.CodeName → exact BPStructureDynamicData.Rows[CodeName]
    BPMount? NO — structure health uses BPStructureDynamicData.MaxHealth
  Default__*.Properties.MaxHealth → independent cross-check if exported
  Default__*.Properties.ArmourType → exact armour enum, if exported
```

Unlike a weapon's fire-component graph, a structure's source identity begins
with the actual Blueprint `CodeName` property. The dynamic table row is then
joined by that **exact** value. Equal health, similar display names, or a
structural family name do not establish identity.

Child Blueprints may inherit `CodeName`, `MaxHealth` or `ArmourType`.
Follow `SuperStruct.ObjectPath` and preserve the actual defining asset and
property path for every inherited field. A missing property after the exported
ancestry terminates at `/Script/War` is **unresolved**, not a default value.

## Real build-26058282 examples

| Blueprint | Explicit `CodeName` | Dynamic health | Exported armour |
|---|---|---:|---|
| `Structures/BPWatchTower` | `WatchTower` | 350 | Not declared in exported ancestry; native/runtime behavior unresolved |
| `Structures/Rail/BPRailTrackSplineFoundation` | `RailTrackSplineFoundation` | 500 | `Tier3BStructure` |
| `Structures/Facilities/BPFacilityVehicleFactory3` | `FacilityVehicleFactory3` | 4650 | `Tier3Structure` |
| `Structures/BPISGPillbox` | `ISGPillbox` | 950 | `Tier2Structure` |

**Important:** An absent `ArmourType` in `BPWatchTower` does not prove
`NoArmour`. The live game's native code may apply additional logic. Preserve
the existing manually reviewed armour assignment until direct evidence
supports a change. Do not reverse-engineer executables as part of this
source-only work.

The two rail-foundation rows in the existing bot sheet show health 750, while
the current named dynamic table rows contain 500. That is a **review finding**,
not authorization to write 500 or change its target category automatically.
Likewise, a coincidentally matching HP on a different developer row cannot
justify renaming a structure.

## Read-only command

On the private, authorized extracted Blueprint directory:

~~~bash
ROOT=/PRIVATE/EXPORT/War/Content/Blueprints
python3 scripts/resolve_structure_blueprints.py \
  --source-root "$ROOT" \
  --structure Structures/BPWatchTower.json \
  --build-id 26058282

python3 -m unittest discover -s test -p 'test_resolve_structure_blueprints.py' -v
~~~

The output contains the source's `CodeName`, explicit property paths, JSON
SHA-256, the exact dynamic health row and any exported/inherited armour.
It carries separate **health** and **armour** statuses; health being resolved
does not imply armour has been verified. All records remain review-only.

The isolated private runner workflow
`Romboter/foxhole-lab` `automation/structure-identity-validation`
checks those relationships against its local pinned PAK using temporary
exports. It does not upload raw asset JSON.

## Required coverage before generation

1. Resolve actual Blueprint identity, including subclass overrides and
   objects with no `CodeName` in exported defaults.
2. Separately match the resulting developer identity to the appropriate bot
   row. Never choose between duplicate/ambiguous candidates using HP alone.
3. Distinguish dynamic health from base-Blueprint health where they disagree;
   report conflicts and retain both source citations.
4. Resolve native-only armour by a separately reviewed evidence process.
   Missing properties must remain unresolved, not silently inferred.
5. Record each exact game build, file and field path, extractor commit and
   current value for deterministic regeneration and audit.
6. Review the known target developer-name mismatches and bunker-tier
   categories as separate identity families.
7. Require approved PR, independent audit backup and live snapshot rollback
   before publishing any generated target change.

Related: [Blueprint connection model](blueprint-reference-model.md),
[game-data audit](game-data-audit.md),
[asset-derived data contract](../superpowers/specs/2026-11-01-asset-derived-data-contract.md).
