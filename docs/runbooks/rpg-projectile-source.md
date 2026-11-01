# RPGAmmo: projectile chains beyond the ammunition DataTable

**Status:** Build `26058282` read-only source investigation; numeric
calculation unresolved. Raw PAK and exported Blueprints stay private.

## What the source graph actually says

Five vehicle-mounted component Blueprints explicitly set
`AmmoName = RPGAmmo`, which has **no exact row** in
`BPAmmoDynamicData` on this build. We must not pretend that the
similarly named `ATRPGAmmo` is equivalent.

However, the same mounted components each export a distinct
`ProjectileClass.ObjectPath` reference. Their projectile Blueprints
declare both an `ExplosiveCodeName` (typically `RpgAmmo` or `RPGAmmo`)
and an `ExplosionTemplate.ObjectPath`.

```text
Vehicle seat MountComponent.ObjectPath
  → mounted projectile-gunner component
      AmmoName = RPGAmmo
      ProjectileClass.ObjectPath
        → WarProjectile Blueprint
            ExplosiveCodeName = RpgAmmo / RPGAmmo
            ExplosionTemplate.ObjectPath
              → WarExplosionEffect Blueprint
```

This provides **additional exact reference evidence**, but not a
numerically authoritative damage row. The explosion assets observed so far
are presentation/effects configurations rather than an established direct
damage source. The case-only spelling difference is recorded, not silently
treated as an alias proving a numeric relationship.

## Observed build-26058282 source chains

| Mount component | Projectile Blueprint | Explosion template |
|---|---|---|
| `BPMechWGunnerComponent` | `BPMechWRocketProjectile` | `BPMechWRocketExplosion` |
| `BPScoutVehicleOffensiveCGunner` | `BPScoutVehicleOffensiveCRPGProjectile` | `RPGExplosion` |
| `BPArmoredCarTwinCGunnerComponent` | `BPArmoredCarTwinCRPGProjectile` | `RPGExplosion` |
| `BPMediumTank2TwinCRPGGunner` | `BPMediumTank2TwinCRpgProjectile` | `RPGExplosion` |
| `BPMediumBoatWBowGunner` | `BPRPGTWProjectile` | `RPGExplosion` |

Source: explicitly exported `AmmoName`, `ProjectileClass`,
`ExplosiveCodeName`, and `ExplosionTemplate` properties. The current
script does **not** establish where native code determines final RPG
damage. No asset name or similar multiplier can substitute for a proven
damage-source edge.

## Read-only investigation

~~~bash
python3 scripts/trace_projectile_source.py \
  --source-root /PRIVATE/EXPORT/War/Content/Blueprints \
  --mount-component Vehicles/Mech/BPMechWGunnerComponent.json \
  --build-id 26058282

python3 -m unittest discover -s test -p 'test_trace_projectile_source.py' -v
~~~

Output includes the original source file, referenced package path, property
path, file hash, exact ammo-name row presence, case-only name differences,
and unresolved evidence gaps. It never emits a generated damage value or
marks any result safe for unattended publication.

## Next proof requirements

1. Determine from an authorized source whether `ExplosiveCodeName` maps
   to another data source, an item profile, or native-only gameplay logic.
2. Require an explicit source relationship before assigning a numeric
   value; do not use `ATRPGAmmo` or a similar row by naming alone.
3. Extend targeted export dependency discovery to `ProjectileClass` and
   `ExplosionTemplate` with bounded private extraction.
4. Validate any discovered numeric rule against a game build and known
   gameplay fixtures, retaining operator review if native-only.
5. Keep these links unresolved in generator outputs until the source
   chain and damage authority are independently established.

Related: [Issue #53](https://github.com/Romboter/aedilebot/issues/53),
[Blueprint graph model](blueprint-reference-model.md),
[asset-derived data contract](../superpowers/specs/2026-11-01-asset-derived-data-contract.md).
