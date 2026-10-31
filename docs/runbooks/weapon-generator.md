# Runbook: Validate and update weapon damage from game exports

**Status:** Generator prototype implemented; offline synthetic tests in CI. Game-build parity must be checked against a pinned export before automation. **Use for:** detecting weapon damage drift, reviewing changes and validating multiplier mappings.

## Inputs and limitations

- Source tables: **BPAmmoDynamicData**, **BPWeaponDynamicData** and **BPMountDynamicData**, exported from authorized game assets under **War/Content/Blueprints/Data/**.
- Destination: **data/Weapons.json**, specifically the **Damage** property. Names, aliases and other curated fields must survive unchanged.
- Overlay: **data_manual/weapon_multipliers.json**. Many weapon-to-multiplier references were seeded by comparing **numerical values**, not proving that the referenced row belongs to that physical weapon. These are *numeric proxies*, not authoritative identity. If independent balance changes affect those rows, the resulting damage would be wrong.
- Kinetic factor: 1.25 for damage types containing Kinetic or for AircraftAmmo. Observed rule, not independently present in exported DataTables.
- Entries without a matching ammo data row remain manually curated.
- Passing synthetic tests does **not** certify a new game version's data.

## Prerequisites

1. Checkout a reviewed development branch. Record commit SHA, Foxhole build ID and exporter SHA.
2. Keep the last reviewed Weapons.json and multiplier overlay available for comparison. The input directory must contain all three valid DataTables.
3. Run the self-contained regression tests from repo root (no game files required):

~~~bash
python3 -m unittest discover -s test -p 'test_gen_weapons.py' -v
~~~

## Inspect data safely

1. Run **read-only** drift detection:

~~~bash
python3 scripts/gen_weapons.py /PATH/TO/EXPORTED/STATS
~~~

Exit 0 and "0 changed" means the generated values match. Exit 1 reports drift; inspect printed differences. Other nonzero exits mean invalid data, options or mappings and must not be ignored.

2. Review each changed field against the pinned game export. Pay special attention to manually mapped weapons, HV/LV annotations, and missing ammo records. A variant-factor check is not proof of physical row identity.
3. **Never run --seed unattended.** It infers multiplier-row selection from matching numbers. After using it for exploration, independently review each mapping before approving any data change.

## Apply after review

1. Use a non-production feature branch with an approved change request.
2. Apply the reviewed values:

~~~bash
python3 scripts/gen_weapons.py /PATH/TO/EXPORTED/STATS --write
git diff -- data/Weapons.json data_manual/weapon_multipliers.json
~~~

3. Ensure only intended **Damage** values changed semantically. The writer may reformat the JSON when values change, so review the complete diff. Do not approve unexpected additions, removals or alias changes.
4. Run the regression tests, Node calculator tests and Python golden fixture checks. Review representative damage calculations; approve and merge only after confidence in the source and mapping.

## Verification and rollback

**Success:** pinned source recorded, all changed values justified, no unexplained mapping, dry-run now reports zero changes, tests pass, and PR has human approval.

**Stop:** invalid/nonfinite damage, missing multiplier, inconsistent HV/LV annotation, unverified numeric mapping, unknown game build or failing tests. Never bypass a failure by blindly re-running --seed.

**Rollback:** revert the reviewed data commit or restore the previous Weapons.json and overlay. If live data had already been loaded, roll back the in-memory dataHost too; on-disk files must be restored before restarting. See [Game data change](data-change.md) and [Hot swap](hot-swap.md).

**Source:** [Generator](../../scripts/gen_weapons.py), [Multiplier overlay](../../data_manual/weapon_multipliers.json), [Phase 4 draft](../superpowers/specs/2026-10-31-phase4-automated-data-pipeline-design.md).
