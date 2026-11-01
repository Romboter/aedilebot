# Inherited vehicle-seat mount source inventory

The read-only tool `scripts/audit_inherited_seat_mount_sources.py` builds on the source-verified SCS component override chain from PRs #70–#75. It is restricted to parent/child source template pairs where **both exact exports** are `VehicleSeatComponent` with verified serialized `Outer` ownership. The pinned Foxhole build `26058282` previously contained **170 such pairs**.

## What it checks

For both sides of each verified seat pair, independently:

- `MountCodeName`: record whether the field was actually serialized; check the original saved string against the exact `BPMountDynamicData` row set and SHA-256 from the build-pinned graph. Treat `None` as an unset candidate, not a row; treat case-only missing row matches only as review diagnostics.
- `MountComponent`: record whether absent, explicitly null, native/external, malformed, or a Blueprint-target `ObjectPath` with a checked graph edge. Record the target package and its SHA-256 if exported, **not** a guessed export or runtime mount.
- Compare presence and canonical source values: neither saved, parent-only, child-only, both saved equal, or both saved different. Missing child fields are *never* filled from parent declarations.
- Preserve exact package hashes, parent SCS node, handler index, parent and child export records, original fields, and mounted-data table hash.

The output is marked `review_only_explicit_seat_mount_source_edges`, `safe_for_unattended_publication=false`, `effective_runtime_mount=not_established`, and `effective_runtime_ammo=not_established`.

## How to reproduce privately

Use the restricted `Romboter/foxhole-lab` workflow on branch `automation/seat-mount-source-survey`. The workflow verifies the pinned game build and exact source and extractor commits before dumping Blueprint JSON into temporary restricted scratch. It generates the graph and all upstream component provenance checks before running the seat-mount audit. It prints only bounded source identifiers and aggregated status counts; no complete export is uploaded.

Standalone invocation after generating its upstream reports:

```bash
python3 -m scripts.audit_inherited_seat_mount_sources \
  --source-root /PRIVATE/War/Content/Blueprints \
  --index /PRIVATE/index.json \
  --qualified-exports /PRIVATE/qualified-exports.json \
  --output /PRIVATE/seat-mounts.json
```

## Deliberate limits

The named DataTable row proves only an *explicit saved source identifier*. It does not prove the original UE `FName` tag, runtime seat weapon, selected ammunition or damage. A `MountComponent` Blueprint package path does not establish the precise target component export; the numeric `.N` suffix is uninterpreted. Both require follow-up independent evidence before promotion.

Runtime CDO and partial `MultiAmmo` inheritance remain open. Do not merge, deploy, publish combat values, schedule downloads or change production bot data based on this inventory.
