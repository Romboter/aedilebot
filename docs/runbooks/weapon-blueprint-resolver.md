# Runbook: Asset-backed weapon resolver (research stage)

**Status:** Working read-only prototype, **not a bot data generator**.
No automatic Steam updates, scheduled checks, production data writes, PR creation,
or hot-swap activation are enabled.

## Contract

`scripts/resolve_blueprint_weapons.py` reads previously extracted, private
Foxhole Blueprint JSON and the named `BPAmmoDynamicData` and
`BPMountDynamicData` rows. It is designed to follow **relationships**, not
`data_manual/weapon_multipliers.json`. Its output records the build supplied
by the operator, source asset and property paths, SHA-256 of source JSON files,
ammunition, actual mount row, damage components and any manually maintained
gameplay factor. It returns unresolved endpoints with reasons; every endpoint
remains ineligible for unattended publication in this stage.

Two supported relationship shapes:

- **Vehicle `WeaponConfigs`**: each array element explicitly connects
  `AmmoCodeName` to `WeaponCodeName`. This yields multiple independent guns
  on the same vehicle, including fighter HMG and cannon.
- **Vehicle seat mounts**: each `VehicleSeatComponent` supplies
  `MountCodeName` and a `MountComponent` asset reference. The resolver
  follows `SuperStruct` references up the Blueprint inheritance chain
  until the nearest declared `AmmoName` or `MultiAmmo` property is found.
  Ambiguous multi-ammo mounts remain unresolved in this prototype.

The named mount must exist in `BPMountDynamicData`; the explicit ammo name
must exist in `BPAmmoDynamicData`. No fallback by matching a multiplier,
display name, prefix, or previously known damage is permitted.

## Run against the private archived export

The previously archived research ZIP is
`foxhole-weapon-asset-research.zip`, 3,795 Blueprint packages, game build
`26058282`; it must remain private. Its root contains
`export/War/Content/Blueprints`. Examples below must run only in a private
workspace with legally obtained exports.

~~~bash
# From the AedileBot repository root:
ROOT=/PRIVATE/foxhole-weapon-asset-research/export/War/Content/Blueprints

python3 scripts/resolve_blueprint_weapons.py \
  --source-root "$ROOT" \
  --vehicle Vehicles/Aircraft/AircraftFighterW/BPAircraftFighterW.json \
  --build-id 26058282

python3 scripts/resolve_blueprint_weapons.py \
  --source-root "$ROOT" \
  --vehicle Vehicles/Aircraft/AircraftWaterW/BPAircraftWaterW.json \
  --build-id 26058282

python3 scripts/resolve_blueprint_weapons.py \
  --source-root "$ROOT" \
  --vehicle Vehicles/LargeShips/DestroyerC/BPLargeShipDestroyerC.json \
  --build-id 26058282

python3 -m unittest discover -s test -p test_resolve_blueprint_weapons.py -v
~~~

### Independently reproduced build-26058282 references

These relationships were verified against the locally archived JSON export,
with exact mounted rows checked against the DataTables.

| Source Blueprint | Firing endpoint | Ammunition | Actual mount row | Multiplier | Calculated direct damage |
|---|---|---|---|---:|---:|
| `BPAircraftFighterW` | `WeaponConfigs/0` | `AircraftAmmo` | `AircraftFighterW_HMG` | 1.00 | 81.25 |
| `BPAircraftFighterW` | `WeaponConfigs/1` | `ATRifleAmmo` | `AircraftFighterW_Cannon` | 1.50 | 281.25 |
| `BPAircraftWaterW` | `WeaponConfigs/0` | `AircraftAmmo` | `AircraftWaterW_HMG` | 1.25 | 101.5625 |
| `BPLargeShipDestroyerC` | `GunnerSeat4`, `GunnerSeat5` | inherited `MGAmmo` | `LargeShipDestroyerCMachineGunner` | 1.20 | 82.5 |

The kinetic/aircraft 1.25 factor is still a **manually maintained gameplay
rule**. These numbers are *not* an assertion of verified live combat damage.

The Destroyer chain uses the referenced
`BPLargeShipDestroyerCMachineGunner` component and inherited
`BPColVehicleMachineGunnerComponent.AmmoName`. The same scan
also found artillery, direct gun and depth charge seats, and left spotter
and sonar seats without an ammunition relationship rather than guessing.

### Existing sheet discrepancies exposed

- The bot's `Luminary Mk. II Harbinger 14.5mm (+50% HV)` currently names
  `AircraftFighterW_HMG`, while its `ATRifleAmmo` belongs to
  `AircraftFighterW_Cannon`. The existing 281.25 number agrees numerically,
  but **the firing mount identity is wrong**.
- `Tulka I1.9 White Raven 20mm (+25% HV)` currently lists
  `AircraftFighterW` and `AircraftFighterW_Cannon`. The exported
  `BPAircraftWaterW` machine gun fires `AircraftAmmo` with a 1.25
  multiplier, but **its display identity is still unconfirmed**.
- The generic `Ship 12.7mm (+20% HV)` entry still uses an unrelated
  `AssaultRifleHeavyW` multiplier proxy. The Destroyer connection is
  asset-backed but **cannot be generalized to every ship**.

Do **not** edit those shared sheet entries until display-to-asset identity
is verified, including any other vessels sharing a generic row.

## Private runner

A separate, non-scheduled workflow lives in private
`Romboter/foxhole-lab` branch
`automation/weapon-resolver-validation`. It uses a pinned public resolver
commit plus a separately pinned CUE4Parse extractor, checks the **readable
local Steam build ID**, and performs read-only extraction to a temporary
directory. No PAK, raw JSON, credential, or source archive is uploaded.
Reports go to the private Actions step summary, not the public repository.
The workflow has no SteamCMD invocation and no write token for the bot.

## Before integration

1. Re-run and compare outputs on the private runner with the pinned build,
   PAK hash and exporter commits. Preserve an independent archive and audit
   trail under controlled permissions.
2. Enumerate every firing endpoint, including infantry weapon items, tanks,
   ships, aircraft, tripods and emplacements. Extend explicit inheritance
   and multiple ammo handling without guessing.
3. Keep vehicle identity, sheet display identity and firing endpoint as
   separate keys; one vehicle can expose more than one gun.
4. Treat native-only values as explicit versioned rules and record their
   review evidence. Avoid reverse engineering executable gameplay until
   assets and license constraints have been reviewed.
5. Derive a **new candidate bundle**, check values and aliases, compare
   goldens, and open only human-reviewed PRs once independent backups and
   snapshot rollback are proven. Do not automatically publish from this
   research script.

Related: [asset-derived data contract](../superpowers/specs/2026-11-01-asset-derived-data-contract.md),
[weapon identity evidence](weapon-asset-tracing.md), [Issue #44](https://github.com/Romboter/aedilebot/issues/44).

## MultiAmmo is a set of explicit alternatives, not one default

The Blueprint connection graph can expose multiple valid ammunition values
for one firing mount. `MultiAmmo.CompatibleAmmoNames[]` is a list of
**source-linked alternatives**, and each member has its own
`BPAmmoDynamicData` row. Do not select the first option simply to produce
one `Weapons.json` entry.

Examples independently checked against build `26058282`:

- `BPHalfTrackArtilleryC` mortar mount `HalfTrackMortarGunner`:
  `MortarAmmo`, `MortarAmmoSH`, `MortarAmmoFL`, `MortarAmmoFlame`.
- `BPSuperTankW` front grenade mount
  `SuperTankWGrenadeLauncherGunner`:
  `HELaunchedGrenade`, `SmokeGrenade`, `GreenAsh`, `GrenadeW`,
  `ATLaunchedGrenadeW`.

The resolver returns an unresolved **parent firing endpoint** and a
`variant_candidates` array with source-backed direct damage calculations
for each compatible ammo. Even when every candidate is numerically resolved,
none is automatically selected for publication. Variant selection and
display/vehicle identity must be reviewed separately.

`Damage = 0` in a named ammo row can be an accurate **zero direct-damage**
value (flare, gas or smoke), not a missing source. Do not infer secondary
effects, damage-over-time mechanics or target mitigation from that zero.

## Discovering the required export packages

`scripts/find_blueprint_dependencies.py` scans extracted JSON for the
**explicit edge types currently used by the resolver**:

- `BlueprintGeneratedClass.SuperStruct.ObjectPath` (parent classes)
- `VehicleSeatComponent.Properties.MountComponent.ObjectPath` (gun mounts)
- `Default__*.Properties.ItemComponentClass.ObjectPath` (infantry item components)

Use it to produce a list of referenced but unexported Blueprint packages
that must be fetched privately:

~~~bash
python3 scripts/find_blueprint_dependencies.py \
  /PRIVATE/OUTPUT/War/Content/Blueprints \
  --output /PRIVATE/OUTPUT/missing-blueprints.json

python3 -m unittest discover -s test -p 'test_find_blueprint_dependencies.py' -v
~~~

This is **dependency discovery, not proof that the game asset is missing**.
The scanner intentionally does not crawl every arbitrary `ObjectPath`
(e.g., materials or FX), and it must not cause arbitrary new packages to be
published to GitHub. The private extractor can fetch exact package paths
from the returned list in a separately bounded, read-only workflow.
