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
