# Saved ammunition declarations on source-verified seat mount Blueprints

This read-only stage builds on Issue #76 and the exact saved MountComponent generated-class links from draft PR #78. The pinned Foxhole build `26058282` contains 124 explicitly saved mount class references across 170 inherited `VehicleSeatComponent` parent/child pairs; the 124 class references each have exactly one saved `Default__<Class>_C` object.

`scripts/audit_mount_class_saved_ammo.py` reopens each exact target package with indexed SHA-256, confirms that its `BlueprintGeneratedClass` and saved class-default export are unique, and records only the **explicitly serialized source property surface**.

Fields inventoried: `AmmoName`, `CompatibleAmmoCodeName`, `MultiAmmo`, `GrenadeMultiAmmo`, `WeaponConfigs`, `ProjectileClass`, `ProjectileClasses` and `ExplosionTemplate`. Missing fields are `not_serialized`, not inferred from a parent. Saved `MultiAmmo` structs without `CompatibleAmmoNames` remain **partial**; explicitly empty arrays are distinguished from omitted fields. Saved options are source declarations, never effective runtime selections.

The tool also records the explicit `SuperStruct` Blueprint package candidate of each mount class, without automatically merging any values. The build-pinned graph and all exact source package hashes must pass validation. No game-export JSON or complete saved-value reports are committed to the repository.

## Reproduction

Use the restricted `Romboter/foxhole-lab` workflow branch `automation/seat-mount-saved-ammo-surface`, which verifies the pinned game build and exact app/extractor commits, runs the upstream SCS/seat/mount provenance pipeline, and prints derived field-shape counts only. All full reports stay in temporary private scratch.

```bash
python3 -m scripts.audit_mount_class_saved_ammo \
  --source-root /PRIVATE/War/Content/Blueprints \
  --index /PRIVATE/index.json \
  --mount-class-report /PRIVATE/mount-classes.json \
  --output /PRIVATE/mount-ammo-saved.json
```

## Proof boundaries

This stage does not establish original nested UE4.24 tagged field types, effective runtime CDO defaults, inherited `MultiAmmo` list reconstruction, selected ammo variants, weapon firing behavior, mount DataTable factors or damage. A saved class default is *not* necessarily the effective child component value. Do not promote guessed values from parent classes, use list indexes to pair ammo and multipliers, publish automatic damage, merge upstream, schedule game updates or change production bot data.

Next: for mount classes with absent saved `AmmoName` or partial `MultiAmmo`, trace explicit `SuperStruct` ancestor CDO source declarations with exact field-local provenance, preserving all unresolved effective runtime states.
