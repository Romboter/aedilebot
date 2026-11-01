# Runbook: Trace weapon/mount/ammo references in Foxhole exports

**Status:** Research tooling only. Tested with synthetic UnrealExporter-style JSON; a complete real weapon-to-mount-to-ammo relationship has NOT yet been verified from licensed Foxhole exports. **Use for:** distinguishing actual game-asset references from numerical multiplier coincidences.

## What counts as an asset-backed relationship?

A convincing evidence chain needs (1) the real game Blueprint or development ID corresponding to the weapon or vehicle, (2) the exact barrel/mount that fires it, (3) that barrel's/ammunition's actual game-asset reference, and (4) the real firing weapon or mount's damage multiplier. Preserve source path, property path, game build, and exporter version at every hop.

**Numerical equivalence is not proof.** Same-name prefixes and two identifiers appearing within the same actor are also insufficient. One vehicle may contain multiple mounts and ammo types. Native code and inherited Blueprint defaults may hold relationships that simple exports omit.

## Prerequisites

- Privately retained, authorized game-export JSON from one pinned Foxhole build, including Blueprints/Data AND class defaults for relevant weapons, mounts and vehicles. Exporting only DataTables or map actors is insufficient.
- Python 3.12+ and a matching data/Weapons.json.
- Keep all game assets and raw evidence reports **outside the public repository**.

## Search a known weapon

From the repo root:

~~~bash
python3 scripts/trace_weapon_assets.py "/PRIVATE/EXPORT/War/Content/Blueprints" \
  --weapons-json data/Weapons.json \
  --weapon "Ship 12.7mm (+20% HV)" \
  --output "/PRIVATE/ship-mg-references.json"
~~~

The sheet lists this weapon's ammunition development name as MGAmmo, without a verified mount. The tracer uses that ID, NOT the numerical-proxy AssaultRifleHeavyW row. Investigate which Blueprint owns each ammo reference, then follow its mount/weapon references and the corresponding multiplier.

Once a **verified** mount ID is identified:

~~~bash
python3 scripts/trace_weapon_assets.py "/PRIVATE/EXPORT/War/Content/Blueprints" \
  --ammo MGAmmo --mount VERIFIED_MOUNT_DEV_NAME \
  --output "/PRIVATE/ship-mg-mounted-references.json"
~~~

Some Weapons.json entries also provide Vehicle Dev Name and Mount Dev Name; the scanner uses those as search hints, not proof of relationships.

## Interpret the report

- matches: per-asset-object candidate references with source file, object, JSON property path, referenced text, and matched ID.
- roles_present: identifiers co-occurring **within one exported object**; not automatically proof of which ammo a mount fires.
- invalid_json_files: incomplete/unparseable inputs. Investigate, do not claim complete coverage.
- status: explicitly says these are unverified evidence candidates.
- No matches: missing export coverage, alternate IDs, class inheritance or native implementation are all possible. It does NOT prove no relationship exists.

The scanner never matches multiplier numbers or arbitrary item display descriptions.

## Verification and rollback

Offline test:

~~~bash
python3 -m unittest discover -s test -p 'test_trace_weapon_assets.py' -v
~~~

For each proposed real relationship, inspect the original source asset and link the exact firing mount to the ammo and multiplier from the *same game build*. Request a second reviewer before replacing any numeric proxy. Unresolved links should remain unresolved; do not auto-publish guessed damage changes.

The tracer reads exports and data/Weapons.json only. It can write an optional private JSON evidence report but never edits damage values, overlay mappings or game assets. If evidence conflicts, stop and leave the generator untouched.

**Related:** [Issue #44](https://github.com/Romboter/aedilebot/issues/44), [Phase 4 research](../superpowers/specs/2026-10-31-phase4-automated-data-pipeline-design.md), [Game-data updates](data-change.md).

## Destroyer 12.7mm MG: operator-reported asset chain (pending pinned-build verification)

A concrete asset chain was supplied for the **Colonial Destroyer** only:

| Relationship | Reported source field/value |
|---|---|
| Vehicle Blueprint | `BPLargeShipDestroyerC` |
| Seats | `GunnerSeat4` and `GunnerSeat5` |
| Seat `MountCodeName` | `LargeShipDestroyerCMachineGunner` on each seat |
| Actual mounted class | `BPLargeShipDestroyerCMachineGunner` |
| Inherited component class | `BPColVehicleMachineGunnerComponent` |
| Inherited ammunition | `MGAmmo` |
| Named mount multiplier row | `BPMountDynamicData.LargeShipDestroyerCMachineGunner` |
| Reported multiplier | `1.20` |

The existing `Ship 12.7mm (+20% HV)` generator overlay currently uses the unrelated
`Weapon:AssaultRifleHeavyW` numerical proxy. The proposed **Destroyer-only** replacement is
`Mount:LargeShipDestroyerCMachineGunner`, **not yet applied**.
A shared `Ship 12.7mm` sheet entry does not prove all vessels fire through this same mount.

The structured, explicitly **unverified** research record is
`data_manual/weapon_asset_identity_candidates.json`. The status means the claim has not
yet been independently corroborated against a specific, hashed licensed export.
Do not mark it verified or authorize generation merely because 1.20 happens to match.

### Non-destructive checks

From the AedileBot repo root:

~~~bash
python3 scripts/validate_weapon_identity_candidates.py

# Optional: validates the *named* mount row on a privately held DataTable export;
# this is still not proof of the seat → mount → inherited ammo chain.
python3 scripts/validate_weapon_identity_candidates.py --stats /PRIVATE/OUTPUT/stats

# Independently inspect reference candidates from private full Blueprint exports.
python3 scripts/trace_weapon_assets.py /PRIVATE/EXPORT/War/Content/Blueprints \
  --ammo MGAmmo \
  --mount LargeShipDestroyerCMachineGunner \
  --vehicle BPLargeShipDestroyerC \
  --output /PRIVATE/destroyer-mg-trace.json
~~~

For a **full identity sign-off**, pin the game build ID, vanilla PAK SHA-256, exporter
revision and SHA-256 hashes of reviewed source assets in the private audit system.
Inspect the original `BPLargeShipDestroyerC` Blueprint exports at both gunner seats,
verify `MountCodeName` resolves to the named actual mount class, verify the
`BPColVehicleMachineGunnerComponent` inheritance/default ammunition chain, and
verify the **same-build** `BPMountDynamicData` row. Record exact private asset and
property paths and a second reviewer's approval. Do not put raw exports in this
public repository.

**Fail-closed rule:** no source path, no build/hash, or a missing inheritance edge
means the claim remains a pending candidate. This research ledger is never consumed
by `gen_weapons.py`; do not turn on scheduled updates or automatic production
writes. Once source-verified, update the multiplier overlay through a separately
reviewed PR and check the calculator fixtures and scope for other ship MGs.
