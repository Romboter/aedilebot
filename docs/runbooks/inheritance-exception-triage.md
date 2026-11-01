# Runbook: incomplete mount and MultiAmmo Blueprint inheritance

**Scope:** Read-only graph research. Game build `26058282`. This is not
automatic damage generation, Steam update monitoring, or production activation.

## Why this diagnostic exists

The build-wide named-row audit and typed-`FName` verification established
10 uniquely linked case-only identities and two `FName(None)` unset
driver seats. The remaining six declarations have different unresolved
causes. Grouping them together as "missing damage" would hide the
relationship we still need to prove.

The source cases are:

| Source | Field / problem |
|---|---|
| `Vehicles/BattleTanks/BattleTankBase` / `MachineGunnerSeat2_GEN_VARIABLE` | `MountCodeName=BattleTankMachineGunner` absent from named mount rows |
| `Vehicles/FieldWeapons/BPFieldMortarBase` / `PassengerSeat1_GEN_VARIABLE` | `MountCodeName=FieldMortarGunner` absent from named mount rows |
| `Items/BPATRPGLightCItemComponent` | `MultiAmmo` lacks exported compatible options |
| `Vehicles/LightTank/BPTrainCombatCarWGunnerComponent` | `MultiAmmo` lacks exported compatible options |
| `Vehicles/LightTank/BPTrainCombatCarWRearGunnerComponent` | `MultiAmmo` lacks exported compatible options |
| `Vehicles/MediumTank/BPMediumTank2CGunnerMountComponent` | `MultiAmmo` lacks exported compatible options |

## Evidence approach

**Mounts:** Start at each *exact* base Blueprint `SuperStruct` class,
reverse its exported inheritance edges to discover descendants, and
assemble same-named seat properties from base to derived. Record the
defining source package and source SHA for the effective
`MountCodeName`. Distinguish a subclass that retains the missing
base name, explicitly overrides it with a named mount row, or doesn't
export that seat. Do not infer that a descendant is spawnable or active
based on an inheritance edge alone. A missing `BPMountDynamicData` row
must never be repaired by a similarly named weapon or matching damage.

**Ammunition:** Follow the actual component class's `SuperStruct`
chain, recording every explicitly exported `MultiAmmo` declaration.
Then inspect all exported subclasses for overrides. An explicitly
missing/null/empty `CompatibleAmmoNames[]` and a valid child override
are different findings. Preserve separate `AmmoName`,
`CompatibleAmmoCodeName`, `GrenadeMultiAmmo`, and projectile-class
references as *possible additional source relationships*, never a
replacement or inferred default for `MultiAmmo`.

The diagnostic's report is always
`review_only_inheritance_exception_inventory` with
`safe_for_unattended_publication=false`. It is deterministic,
bounded to 512 descendants per case, verifies a pinned graph index and
named mount DataTable SHA, and refuses missing/cyclic parent chains.

## Private read-only command

~~~bash
python3 -m scripts.index_blueprint_graph \
  --source-root /PRIVATE/extracted/War/Content/Blueprints \
  --build-id 26058282 \
  --output /PRIVATE/scratch/index.json

python3 -m scripts.triage_blueprint_inheritance_exceptions \
  --source-root /PRIVATE/extracted/War/Content/Blueprints \
  --index /PRIVATE/scratch/index.json \
  --output /PRIVATE/scratch/triage.json

python3 -m unittest discover -s test \
  -p 'test_triage_blueprint_inheritance_exceptions.py' -v
~~~

The private `Romboter/foxhole-lab` workflow
`automation/inheritance-exception-validation` re-extracts its
authorized local PAK into temporary restricted storage, produces the
graph, and prints a small *derived* inventory as its job summary.
It neither uploads the raw game exports nor modifies the running bot.

## Publication and follow-up gates

- A reference from a base class is not enough to establish which real
  vehicle mounts or ammunition modes it implements at runtime.
- Missing exported options can mean absent data, intentional optional
  mode, or a native/inherited default; only explicit relationships
  establish identity.
- Review child seat/weapon identity and ammunition variants before
  any generator consumes results.
- Preserve off-host audit backup, human-reviewed game-update PR,
  and atomic production snapshot rollback as separate release gates.
- No SteamCMD update, scheduler, auto-merge, generated data writes
  or runtime snapshot changes in this work.

Related: [typed FName row identity](typed-fname-row-identity.md),
[Blueprint build index](blueprint-build-graph.md),
[Issue #58](https://github.com/Romboter/aedilebot/issues/58).
