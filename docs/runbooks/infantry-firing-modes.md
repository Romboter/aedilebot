# Infantry firing modes and ammunition variants

**Status:** Research only; Foxhole build `26058282`. No generated bot data
or automatic updates are authorized.

## Why this is a separate graph problem

A pickup has a primary firing component, but some components expose an
additional rifle-grenade system. The two modes must not share damage
multipliers by assumption.

```text
ItemPickups/BPRifleHeavyWPickup
  Default__*.CodeName = RifleHeavyW
    → BPWeaponDynamicData.RifleHeavyW
  Default__*.ItemComponentClass.ObjectPath
    → ItemPickups/RifleHeavyWComponent
       CompatibleAmmoCodeName = RevolverAmmo
         → BPAmmoDynamicData.RevolverAmmo    [primary fire]
       GrenadeMultiAmmo.CompatibleAmmoNames[]
         → BPAmmoDynamicData.GreenAsh
         → BPAmmoDynamicData.GrenadeW
         → BPAmmoDynamicData.ATLaunchedGrenadeW    [grenade attachment]
       GrenadeClasses[]
         → BPDeadlyGasGrenade
         → BPGrenadeW
         → BPATLaunchedGrenadeW
```

There is an *array of compatible ammunition names* and a separate *array
of referenced grenade classes*. Even if both arrays contain three entries
in the same apparent order, their pairing and shared multiplier are not
independently established by an explicit exported association. Preserve
both as evidence; **do not join by position** without more game-source
evidence.

On the pinned export, four independently observed item components
declare a rifle-grenade mode:

| Item component | Observed primary ammo | Grenade ammo options |
|---|---|---|
| `RifleHeavyWComponent` | `RevolverAmmo` | `GreenAsh`, `GrenadeW`, `ATLaunchedGrenadeW` |
| `BPCarbineComponent` | `RifleAmmo` | same three |
| `RifleLongWComponent` | `RifleAmmo` | same three |
| `RifleComponent` | `RifleAmmo` | same three |

Those are **four separate component definitions**, not four complete
player-facing weapon descriptions. The pickup's explicit
`ItemComponentClass` supplies the identity join.

There is another related but distinct grammar on some launcher
components: `MultiAmmo.CompatibleAmmoNames[]` alongside
`ProjectileClasses[]`. For example, the `BPATRPGCPickup` component
declares `ATRPGAmmo` and references `BPATRPGCProjectile`. Do not treat
`ProjectileClasses` as a rifle-grenade mode or infer which projectile
corresponds to which ammo index without game evidence.

## Run the read-only tracer

From the AedileBot source root, against privately archived licensed
Blueprint JSON exports:

~~~bash
ROOT=/PRIVATE/EXPORT/War/Content/Blueprints
python3 scripts/trace_infantry_firing_modes.py \
  --source-root "$ROOT" \
  --pickup ItemPickups/BPRifleHeavyWPickup.json \
  --build-id 26058282
~~~

The output includes the independently resolved primary-fire chain,
separate secondary ammo options and projectile references, each named
source row, raw ammo damage (including legitimate zero-direct-damage gas),
damage type, inherited property location and source SHA-256. It never
generates a secondary firing-mode damage number or assumes a primary
`BPWeaponDynamicData.DamageMultiplier` applies to the grenade launcher.

The new dependency inventory also follows explicit
`ProjectileClass`, `ProjectileClasses[]`, `GrenadeClasses[]`, and
`ExplosionTemplate` references, in addition to existing inheritance
and mounted-component edges, so private extraction can identify missing
packages without a hand-maintained list.

## Unresolved until further evidence

- The actual selector mapping ammunition variants to their projectile
  classes and the correct per-firing-mode damage/range behavior.
- Native gameplay rules and any separately applied factor.
- Player-facing item/attachment identity where one component is shared.
- Complete dependency closure on new game builds; missing exported
  packages must be reported, not fabricated.

Research only: no SteamCMD updates, scheduled CI, numeric corrections
to production, automatic PR publication, or live snapshot activation.
See [Blueprint reference model](blueprint-reference-model.md),
[Issue #44](https://github.com/Romboter/aedilebot/issues/44).

## Whole-archive known-edge coverage snapshot

A non-destructive pass over the **3,795 Blueprint JSON packages** in the
privately archived build `26058282` counted **870 exact exported references
to other Blueprint packages**, targeting **528 distinct package names**.

| Recognized `ObjectPath` field | Exported references | Missing referenced packages |
|---|---:|---:|
| `BlueprintGeneratedClass.SuperStruct` | 311 | 1 |
| `VehicleSeatComponent.MountComponent` | 300 | 0 |
| `Default__.ItemComponentClass` | 144 | 0 |
| `Default__.ExplosionTemplate` | 43 | 0 |
| `Default__.GrenadeClasses[]` | 31 | 0 |
| `Default__.ProjectileClass` | 31 | 0 |
| `Default__.ProjectileClasses[]` | 10 | 0 |
| **All seven recognized fields** | **870** | **1** |

The one absent referenced package in this archive is
`War/Content/Blueprints/BPWaterStencilComponent`, linked from
`Vehicles/LargeShips/SubmarineW/BPSubmarineStencilComponent`
through `SuperStruct.ObjectPath`. That is an **archive completeness
gap**, not proof that a weapon is broken or that the PAK lacks the
asset. The resolved edge count is 869/870 **for this recognized field
set only**.

Do not interpret 869/870 as coverage of *all* Unreal object references
or gameplay dependencies: the scanner intentionally excludes many
object types, actor/level relationships, runtime links, materials, sounds,
native functions, and implicit DataTable lookups. Treat this inventory
as a **baseline for graph-schema drift comparisons**, not a license to
automatically generate all damage numbers.

`find_blueprint_dependencies.py` reports the count of each recognized
edge type, missing source edges with their exact property and
export-file SHA-256, and the missing package path. No full private JSON
exports are committed with the report.
