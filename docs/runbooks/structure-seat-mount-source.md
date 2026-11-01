# Structure-seat saved weapon source inventory

The main vehicle mount pipeline only covers `VehicleSeatComponent`; the original [upstream calculator](https://github.com/olted/aedilebot/blob/main/src/calculator.py) also needs defensively mounted weapons and structure turrets. A pinned `26058282` source survey, [#41345485604](https://github.com/Romboter/foxhole-lab/actions/runs/41345485604), found **42 saved** `StructureSeatComponent.MountComponent` and **42 saved** `StructureSeatComponent.MountCodeName` declarations. Their exact structure/mount owners were not yet established by the vehicle-only resolver.

`scripts/audit_structure_seat_mount_sources.py` scans exact indexed `Structures/` packages and their saved `StructureSeatComponent` exports, revalidating each file's SHA-256. For every component it separately inventories:

- The saved `Outer` generated-class owner, requiring a matching saved generated class export in that exact source package. This is a source ownership relationship, **not** an SCS node/runtime component identity.
- `MountCodeName` as an explicitly saved string and whether an exactly matching key exists in the SHA-checked `BPMountDynamicData` rows. Missing names, `None`, case-only candidates and absent fields are never guessed or inherited. The original `NameProperty` tag has not yet been independently inspected for these components.
- `MountComponent` saved `ObjectPath` and `ObjectName`, exact indexed target-package identity, unique `BlueprintGeneratedClass` export identity and count of exact saved class-default exports. An Unreal numeric `.N` path suffix is **never** used as an export index.

All references and values remain source-only. Reports explicitly mark effective seats, mounts, ammunition, firing behavior and damage as **not established**. A component in the structure export does not prove that a live object uses it; saved parent fields are not automatically inherited into child templates.

## Reproduce

On the restricted private `foxhole-lab` runner, using the pinned Steam build and immutable source+extractor commits:

```bash
python3 -m scripts.index_blueprint_graph \
  --source-root "$ROOT" --build-id 26058282 --output "$SCRATCH/index.json"
python3 -m scripts.audit_structure_seat_mount_sources \
  --source-root "$ROOT" --index "$SCRATCH/index.json" \
  --output "$SCRATCH/structure-seat-mounts.json"
```

The complete report must remain in restricted temporary scratch. The runner emits only bounded coverage counts and selected source package names, no raw exports, source property contents or production data files.

## Next validation

Compare saved structure seat template identities with `SCS_Node` owner/name/GUID relationships and child `InheritableComponentHandler` template overrides. Independently inspect the original UE type of `MountCodeName`. Any target mount class may save its own ammunition fields, but that does not establish effective runtime ammo selection or damage until inheritance and AI turret behavior are verified. Follow Issue #84.

No upstream pulls, merges, automatic catalog updates, Steam scheduling, production bot writes or raw export uploads.

## Verified pinned results (2026-11-01)

[Private run #41347071275](https://github.com/Romboter/foxhole-lab/actions/runs/41347071275) **PASS**: 19/19 synthetic/regression tests, 0 extractor build errors, build `26058282` and exact relation digest `8a0a8b7c4fa26469b08ca8d39881a69d9beef06f17f520e6472ef8a1676a5a44`.

- 54 saved `StructureSeatComponent` exports with 54 exact source-owning generated-class `Outer` relationships.
- 42 explicitly saved `MountCodeName` declarations, each matching an exact `BPMountDynamicData` row key (not original property-type proof).
- 42 explicitly saved `MountComponent` references; 35 point to unique saved Blueprint-generated class exports; 7 point to native/external targets.
- 12 structure seats omit both mount fields in their own saved export. No missing value was inherited or guessed.

The owner match is saved source ownership only. Neither field's runtime effect has been established. Structure turret/AI firing rules and child/parent SCS template selection require separate validation.
