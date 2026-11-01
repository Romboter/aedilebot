# Calculator-relevant asset field provenance (read-only research)

## Purpose

The original upstream AedileBot calculator needs a weapon's damage, damage type, target health/mitigation category, and special bunker/disable rules. The initial 4,203-package domain survey (restricted run #41344423142, build `26058282`) found **34 `DamageTypes/` packages**, **1,019 `Structures/` packages** and **2,151 `Vehicles/` packages**. The `Structures/` assets explicitly save some `Health`, `MaxHealth`, `ArmourType`, `DamageAttributes` and `DamageAttributesAlternate` fields, but field presence is not a proven effective value.

This stage surveys **source property shapes and hashes**, not the mitigation matrix or automatic target catalog entries.

## Scope and execution

`scripts/audit_calculator_field_sources.py` opens exact SHA-256-checked package JSON for `DamageTypes`, `Structures`, `Vehicles`, `Items` and `Data`. It verifies the index's semantic relationship digest before auditing. Results include source package, source hash, named export, export type, whether it is a saved class default or component template, field, value shape, nested source keys and SHA-256 of the explicitly serialized field value. All records carry `runtime_effective=not_established`.

The scan inventories damage-type generated classes and saved parent `SuperStruct` source candidates. It also inventories DataTable row **field shapes**, not game numerical values or row identifiers, to locate possible damage/repair/mitigation tables.

```bash
python3 -m scripts.index_blueprint_graph \
    --source-root "$ROOT" --build-id 26058282 --output "$SCRATCH/index.json"

python3 -m scripts.audit_calculator_field_sources \
    --source-root "$ROOT" --index "$SCRATCH/index.json" \
    --output "$SCRATCH/calculator-source.json"
```

The pinned private `foxhole-lab` workflow branch is `automation/combat-field-source-survey`; its workflow is `.github/workflows/calculator-field-source-survey.yml`. It checks `foxrunner` and Steam manifest build, compiles the pinned extractor `76ab955b5ad3ebffcdb9a8422c4225c17f9ec185`, runs synthetic tests, and extracts to `umask 077` temporary scratch. It prints only bounded counts and original saved property *names/shapes*, not raw PAK exports or values.

## Evidence boundaries

- `DamageTypes/` package names are source identity only, **not** a mapping to `data/Damage.json` keys or target mitigation categories.
- A structure class default `Health` or `ArmourType` is a saved property, not a verified runtime health/category. Values absent from a child may have native, inherited or component sources.
- A source `DamageAttributes` struct is not automatically weapon damage; its original UE property tags and owner need further validation before any edge is promoted.
- DataTable row shapes do not prove what rule consumes those rows.
- Unknown native `/Script/War` behavior, missing effective class defaults, aliases, armor/penetration rules, bunker integrity and wet-shelter scenario rules remain unresolved.
- Field hashes can flag changes without publishing source values. They do not establish runtime correctness.

## Next step

Inspect pinned field-shape summary, then implement **one** exact typed linkage (for instance, target `ArmourType` declaration to a known damage category, if its original type and semantics are independently established). If matrix factors are not serializable, report the native boundary and keep the curated matrix under human review.

Do not pull upstream, overwrite `data/` or `data_manual/`, deploy, merge, schedule Steam downloads, or upload game exports.
