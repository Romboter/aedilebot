# Typed Unreal FName row identity resolution (research-only)

**Scope:** read-only, build-pinned classification of exact-case-missing
ammunition and mount identifiers from exported Foxhole Blueprints. No
gameplay damage is calculated or published. Production update scheduling
remains disabled.

## Why case spelling was flagged

A full Blueprint index from build `26058282` found 591 named
ammunition/mount row references: 573 exact-case matches, 14 missing
exact-case matches, and four invalid source identifiers. Some misses
contain a **unique spelling-equivalent table name**, including:

| Exported property value | Named DataTable row |
|---|---|
| `RPGAmmo` | `RpgAmmo` |
| `lighttankammo` | `LightTankAmmo` |
| `HalftrackMultiWGunner` | `HalfTrackMultiWGunner` |

Unlike a Python dictionary's default case-sensitive string lookup, Unreal
Engine `FName` comparisons are case-insensitive. The original serialized
UE property type (not the JSON value's appearance) is the critical
difference. CUE4Parse reads `UDataTable.RowMap` as keys of type `FName`.

**The source evidence required for a typed join:**

1. A verified, specific exported source package, record and property
   (e.g. `Default__BPMechWGunnerComponent_C/AmmoName`), with its
   game-build provenance and original source file hash.
2. The *original UE property tag* for that exact field is `NameProperty`.
   Nested `MultiAmmo.CompatibleAmmoNames[i]` requires inspection of the
   parsed `StructProperty` and its actual `ArrayProperty.InnerType`,
   which must be `NameProperty`. The enclosing struct alone is not proof.
3. The target `BPAmmoDynamicData` or `BPMountDynamicData` is an actual
   `UDataTable` with an `FName` key type.
4. The current exported DataTable SHA-256 agrees with the pinned graph
   index, and the case-insensitive lookup finds **exactly one** named row.
5. Inspection and indexing are performed in the same restricted private
   runner job against the same PAK and Steam build. The PAK SHA-256 is
   recorded; no cross-build sidecar files are reused.

The [private nested source-type
validation](https://github.com/Romboter/foxhole-lab/actions/runs/41281513694)
confirmed `NameProperty` for `MultiAmmo.CompatibleAmmoNames[0]` on
`BPRPGWItemComponent` and `BPSubmarineDeckGunnerComponent`. It also
verified the original `FName` DataTable key types. The standalone
type-inspection implementation is on
`research/60-nested-name-type-inspection`.

## Read-only usage

First, use the private pinned runner to export the full Blueprint source
and run `inspect-types` with an exact-package manifest generated from
the missing/invalid rows in the full build graph. The original UE type
inspection produces tab-separated `TYPE` and `TABLE` lines, without
exporting property values.

~~~bash
python3 -m scripts.resolve_typed_fname_rows \
  --index /PRIVATE/audit/graph-26058282.json \
  --source-root /PRIVATE/extractions/War/Content/Blueprints \
  --inspector-output /PRIVATE/audit/types-26058282.tsv \
  --build-id 26058282 \
  --pak-sha256 /PRIVATE_PAK_SHA256_HEX \
  --output /PRIVATE/audit/typed-fname-review.json
~~~

The CLI requires an actual 64-character lowercase hexadecimal PAK hash,
not the placeholder above. The index, exported DataTables and type
inspection must be generated from the same pinned game source.

The output preserves the original `declared_row` and its exact-case
lookup status. A unique, type-proven `FName` match has status
`typed_fname_unique_row_identity`, and a distinct `matched_row`
spelling. This **does not** mark the value safe for publication or assert
that ammo-specific mechanics and multipliers are understood.

A missing original `NameProperty` tag, missing `FName` table-key proof,
multiple spelling-equivalent rows, missing named rows, invalid/empty
`MultiAmmo` definitions, source hash differences, or build mismatches
must remain unresolved or abort the analysis. It is forbidden to:

- Treat a case-only similarity as a verified edge without original type
  evidence for that *specific field*.
- Pick the first candidate from multiple casefolded rows.
- Choose ammo/projectile variants from array order alone.
- Infer missing native damage, damage-type factors or player-facing names.
- Write generated bot data or enable unattended update/release actions.

## Important distinction

This utility **confirms a typed row identity**, not a full source-backed
weapon damage equation. For example, even if `RPGAmmo` can be uniquely
resolved to the engine-`FName` row `RpgAmmo`, the weapon must still be
traced through its actual firing component and mount, and native behavior
must be modeled separately. Replacing numbers in `Weapons.json` is
not authorized by the identity join alone.

The Python tool consumes a restricted type inspector's plain-text
records. Such a record is **not** a signed cryptographic attestation by
itself. The trust boundary comes from running the inspector and the
source-index comparison together on the controlled, pinned private
runner and retaining audit provenance.

Related: [graph index](blueprint-build-graph.md), [Blueprint reference
model](blueprint-reference-model.md),
[Issue #58](https://github.com/Romboter/aedilebot/issues/58),
[Issue #53](https://github.com/Romboter/aedilebot/issues/53).

## Follow-up: `FName(None)` does not identify a mount

The full-build exception list includes two driver-seat records whose
serialized `MountCodeName` is exactly `None`:

- `Vehicles/Tankette/BPTanketteFlameC` /
  `DriverSeat0_GEN_VARIABLE`
- `Vehicles/Tankette/BPTanketteOffensiveC` /
  `DriverSeat0_GEN_VARIABLE`

`FName.IsNone` is an explicit unset-name sentinel in Unreal. A
`None` mount-name field must not be treated as a missing
`BPMountDynamicData` weapon row or automatically assigned a gun.
The graph index now emits `none_sentinel_candidate` for this
particular source field; the typed resolver emits
`typed_fname_unset_mount_identity` **only after** inspecting that
specific field's `NameProperty` tag. Without the original type
evidence, the candidate remains unresolved.

That leaves two actual unavailable mount row names in the pinned
source: `BattleTankMachineGunner` and `FieldMortarGunner`. These
must still be followed through their actual vehicle subclasses/overrides
before concluding they represent an active firing endpoint.

Four other `MultiAmmo` declarations have no usable exported
`CompatibleAmmoNames[]` array. They are now described as
`no_compatible_ammo_names_exported`, rather than proof the game
assets are corrupt. Some may inherit compatible ammunition or
represent optional modes; the current graph declaration alone
does not establish their runtime meaning.

The source inventory remains intentionally review-only. A typed
`None` sentinel is *not* counted as a newly verified weapon damage
value or ammunition identity.
