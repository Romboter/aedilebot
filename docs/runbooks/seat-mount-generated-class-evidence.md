# Exact saved vehicle-seat MountComponent class references

This read-only research follows [Issue #76](https://github.com/Romboter/aedilebot/issues/76) and builds on the original 170 verified inherited `VehicleSeatComponent` parent/child template pairs from draft PR #77.

The private source-shape survey [run #41330732874](https://github.com/Romboter/foxhole-lab/actions/runs/41330732874) found **124 explicitly saved Blueprint MountComponent references** (51 parent, 73 child). All 124 have a qualified `ObjectName` of the form `BlueprintGeneratedClass'SomeMount_C'` and a Blueprint package `ObjectPath`. All paths have numeric `.N` suffixes, **which this resolver never interprets as export indices**.

The source-only resolver `scripts/resolve_explicit_seat_mount_classes.py` accepts the signed-off source graph and saved seat mount report, reopens each source seat and referenced package with the indexed SHA-256, checks the saved `MountComponent.ObjectPath` and `ObjectName` against the graph edge and exact seat export, and then finds a matching `BlueprintGeneratedClass` export by full exact `Name` and `Type`. It independently counts exact saved `Default__<GeneratedClass>` objects but **does not** promote them into runtime-effective CDOs.

Explicitly missing or native/unexported references remain unresolved. Unsupported names, ambiguous class exports and stale source hashes are never guessed. All output is marked `review_only_explicit_mount_generated_class_exports` with `safe_for_unattended_publication=false`, and runtime mount/ammo `not_established`.

The source inspection also found **seven parent mount-row-missing occurrences but only two distinct saved identities**: `BattleTankMachineGunner` (five references from one base template) and `FieldMortarGunner` (two from one base template). There were no case-only matching rows for either in pinned `BPMountDynamicData`. This does not establish their intended game behavior or mean they are invalid weapons.

## Reproduction

Run `Romboter/foxhole-lab` workflow branch `automation/seat-mount-class-validation` against pinned Foxhole build `26058282`. Keep all raw PAK/JSON exports and complete reports in restricted scratch. Use `--source-root`, `--index`, `--seat-report`, and `--output` with `python3 -m scripts.resolve_explicit_seat_mount_classes` for a standalone private run.

The next research step is to inventory **explicitly saved** mount Blueprint class-default `AmmoName`, `MultiAmmo` and related typed data only where the target generated class identity and saved default export are uniquely established, and to preserve partial/empty structs and all unresolved runtime inheritance. Never infer damage or effective weapon selection from a package link alone.
