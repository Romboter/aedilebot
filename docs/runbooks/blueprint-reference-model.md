# Foxhole Blueprint reference model — build 26058282

**Status:** Findings from a privately retained licensed build-26058282 export and
read-only verification against the isolated `foxhole-lab` runner. This is a
model of *source relationships*, not a generator authorization.

## Why the graph matters

Never decide a weapon's source row by multiplying plausible values, comparing
display-name fragments, or assuming Colonial/Warden prefixes. An exported class
is a **package**, not a complete flattened object: child Blueprints can override
some properties, inherit other properties, and reference entirely different
component packages. An asset identifier is not an association unless an actual
property points to it.

A reference such as
`War/Content/Blueprints/Vehicles/LightTank/BPLightTankGunnerMountComponentW.0`
identifies a package and export index. Resolve the package through its explicit
`ObjectPath`, not by trying to synthesize a filename from a mount code.
The index `.0` or `.1` is not the firing slot number. Retain the original
object reference and field location as evidence.

## Three observed relationship grammars

### 1. Vehicle seat + mounted component

```text
vehicle Blueprint (.json)
  BlueprintGeneratedClass.SuperStruct.ObjectPath
    → possibly one or more parent vehicle Blueprints
  VehicleSeatComponent / GunnerSeat*_GEN_VARIABLE
    MountCodeName → BPMountDynamicData.Rows[exact value]
    MountComponent.ObjectPath → referenced component Blueprint
      BlueprintGeneratedClass.SuperStruct.ObjectPath
        → parent component Blueprints, then possibly native /Script/War
      Default__*.Properties:
        AmmoName → BPAmmoDynamicData.Rows[exact value]
        or MultiAmmo.CompatibleAmmoNames[] → one/many ammo rows
```

The **vehicle** inheritance chain and **mounted component** inheritance chain
are separate. Apply base-to-derived overrides to each *seat field* by exact
seat object name; do not replace the entire inherited seat object when a
child overrides only position or direction.

Verified example:
`BPLightTankC → BPLightTankBaseC → BPLightTankBase`.
`BPLightTankC` redeclares `GunnerSeat1_GEN_VARIABLE` with placement fields;
the parent `BPLightTankBaseC` supplies `MountCodeName=LightTankGunnerC`
and an explicit `MountComponent.ObjectPath` to
`BPLightTankGunnerMountComponentW`. That component's `MultiAmmo` names
`LightTankAmmo`. The named `BPMountDynamicData.LightTankGunnerC` row has
multiplier 1.00, and `BPAmmoDynamicData.LightTankAmmo` has damage 600. The
component happens to have a `W` suffix. This is not a naming rule and
must **not** be remapped to a `C` component by assumption.

The Destroyer class `BPLargeShipDestroyerC` likewise connects seats 4/5 to
`BPLargeShipDestroyerCMachineGunner`, whose parent
`BPColVehicleMachineGunnerComponent` declares `AmmoName=MGAmmo`.
Named mount row `LargeShipDestroyerCMachineGunner` has 1.20 multiplier.

A seat may be a driver, sonar operator, spotter, etc. A missing ammunition
property should be recorded as *unresolved* unless some explicit class/role
evidence proves it intentionally has no firing function. Do not invent ammo.

### 2. Aircraft inline `WeaponConfigs`

```text
vehicle Blueprint Default__*.Properties.WeaponConfigs[i]
  AmmoCodeName → BPAmmoDynamicData.Rows[exact value]
  WeaponCodeName → BPMountDynamicData.Rows[exact value]
```

Each array element is a **separate firing endpoint**. A vehicle may also
have seat-based weapons; process **both** relationship grammars. Preserve the
`MuzzleIndices` when relevant to fire-rate/barrel modeling; it does not
change the source ammo identity.

Build-26058282 references:
- `BPAircraftFighterW`: `AircraftAmmo / AircraftFighterW_HMG` (1.00)
  and `ATRifleAmmo / AircraftFighterW_Cannon` (1.50).
- `BPAircraftWaterW`: `AircraftAmmo / AircraftWaterW_HMG` (1.25).

Display identity (e.g., whether a particular named plane is the White Raven)
is a **separate join** and should never be inferred from numerical agreement.

### 3. Infantry pickup → item component → ammo

```text
ItemPickups/BP...Pickup Default__*.Properties
  CodeName → BPWeaponDynamicData.Rows[exact value]
  ItemComponentClass.ObjectPath → Items/...Component package
    BlueprintGeneratedClass.SuperStruct.ObjectPath
      → optionally parent item-component Blueprint
    Default__*.Properties
      CompatibleAmmoCodeName → BPAmmoDynamicData.Rows[exact value]
      or MultiAmmo.CompatibleAmmoNames[] → zero, one or many ammo variants
```

Examples:
- `BPRifleLightWPickup` (`CodeName=RifleLightW`) refers to
  `BPCarbineComponent`, whose `CompatibleAmmoCodeName=RifleAmmo`.
- `BPAssaultRifleCPickup` (`CodeName=AssaultRifleC`) refers to
  `BPLightMachineGunItemComponent`, which declares `MGAmmo`.
- `BPSniperRifleWPickup` (`CodeName=SniperRifleW`) refers to
  `SniperRifleComponent`, which declares `RifleAmmo`.

The numeric row belongs to the pickup's explicit `CodeName`, **not** to
the item's component classname.

Among 42 directly subclassed `FirearmPickup` Blueprints in the archived
export, all 42 have a matching weapon dynamic row and an exported
`ItemComponentClass` package; 32 directly declare
`CompatibleAmmoCodeName` with a corresponding ammo row. The other ten
require deeper inspection (inherited compatibility, `MultiAmmo`, native
or utility behavior). These figures are **inventory counts**, not 42
complete game-damage validations.

## Source-graph inventory snapshot

A read-only base-to-derived survey of vehicle packages identified:

| Observation | Count |
|---|---:|
| Vehicle-subtree JSON packages examined | 2,151 |
| Seat `MountCodeName` entries across analyzed classes | 350 |
| Seat codes present as named dynamic mount rows | 345 |
| Seat references with an exported mounted-component package | 339 |
| Seat component chains with exactly one declared ammo option | 202 |
| Of those, ammo names present in dynamic ammo rows | 197 |
| Seat chains with multiple declared ammo options | 7 |
| Aircraft `WeaponConfigs` endpoints with matching ammo and mount rows | 9 |

**Important:** The seat counts are per analyzed Blueprint class, including
base and derived variants. They are not distinct in-game vehicle models.
A missing ammo link is **not automatically an error**—some mounts are
controls, native-class-only, or intentionally use multiple ammo types.

These counts were produced from the archive for build 26058282 and should
be regenerated and compared after extractor or game updates rather than
treated as immutable expected totals.

## Resolver implementation and limits

- `scripts/resolve_blueprint_weapons.py` follows vehicle parents
  and merges seat properties by exact component name, resolves
  `WeaponConfigs`, follows mount component parents, and reads named
  ammo/mount rows. It records file hashes and field origins where available.
- `scripts/resolve_infantry_weapons.py` resolves the infantry pickup
  `ItemComponentClass` chain and direct or `MultiAmmo` declarations.
- These prototypes **do not publish**. They do not yet model weapon
  type-specific projectile mechanics, every native rule, all turret classes,
  actor spawn identity, or multiple-ammunition selection. Multi-ammo options
  must remain individually identified; do not choose the first silently.
- The manually maintained 1.25 kinetic/aircraft factor is tagged as a
  gameplay rule, never misrepresented as exported game data.
- The pinned `26058282` build and current private runner export support
  the sampled relationships. Additional classes require per-family
  verification, and any game build transition requires fresh resolution.

## Graph traversal invariants

1. Follow explicit `ObjectPath` and `SuperStruct` edges, with cycle and
   traversal checks. Never infer a link from label, prefix or equal numbers.
2. Retain package, exported record, property path, game build and source
   checksum for each edge. Preserve the source of inherited fields.
3. Discover all firing endpoints and record their actual ammo options.
   A new, missing or ambiguous edge is review-required.
4. Join only named dynamic rows. Missing rows block the numeric result.
5. Separately join game endpoints to the bot's curated names/aliases; scope
   generic rows carefully (one ship may have two guns, different vessels
   can use different mounts).
6. Keep all raw exported packages/private game archives off the public repo.
   Public CI uses synthetic fixtures; the private runner validates the
   pinned real build.
7. Never auto-update production data or enable scheduling until backups,
   full-sheet coverage gates, review PRs and rollback are validated.

Related: [weapon resolver](weapon-blueprint-resolver.md),
[asset-derived pipeline contract](../superpowers/specs/2026-11-01-asset-derived-data-contract.md),
[Issue #44](https://github.com/Romboter/aedilebot/issues/44).
