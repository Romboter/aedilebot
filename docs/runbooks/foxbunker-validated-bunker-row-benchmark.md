# FoxBunker validated bunker tier benchmark against original structure rows

## Scope

The project owner confirmed on 2026-11-01 that FoxBunker's **calculation input data** accurately reflects in-game bunker values. Use the currently fingerprinted public FoxBunker `STRUCTURES` table as the gameplay reference for exploring which *serialized* `BPStructureDynamicData` rows could supply each piece/tier configuration. This remains **candidate discovery**, never an unattended authoritative class/tier map or claim about effective native behavior.

Benchmark source: `https://foxbunker.com/bunker/js/utils.js`, SHA-256 `9f781ca6f7f1d523c4a22f51dd380f0bc2ff38436d829098199de4209f9e69de`. Exact game build `26058282`; original `CodeName` inspector `ad4c97e4bfe719cc24e7e3bb238563d75f49d799`.

## Implementation

`scripts/audit_foxbunker_structure_row_benchmark.py`:

1. Verifies the pinned SHA-256 of publicly served FoxBunker JavaScript and parses the `const STRUCTURES = [...];` **literal**, without evaluating JavaScript.
2. Validates the 22 public piece definitions and all tier-availability and six-value tuple shapes.
3. Uses the verified graph and original `Data/BPStructureDynamicData` file with the exact SHA-256 from that index.
4. Loads `scripts/audit_structure_dynamic_row_identity.py`'s original source type report, checks the build, graph digest, and table SHA, then admits only `original_nameproperty_and_fname_row` saved class joins.
5. Matches **all three values as strict numeric scalars**: `StructuralIntegrity`, `MaxHealth`, `RepairCost`. No strings, booleans, case-only names, fuzzy labels or numeric rounding.
6. Reports `unique_typed_source_row_candidate`, `ambiguous_typed_source_row_candidates`, `unattributed_numeric_row_candidates`, `no_exact_numeric_row_candidate`, or `reference_tier_unavailable`. Multiple matched rows are never silently resolved.
7. Writes complete candidate details only to temporary private runner scratch. Public test fixtures contain invented numbers and labels; no extracted game values or third-party JS source are checked into the fork.

Private workflow: `Romboter/foxhole-lab`, `.github/workflows/foxbunker-typed-structure-benchmark.yml`, branch `automation/foxbunker-exact-structure-row-benchmark`. It checks the dedicated runner user and pinned Steam build, asserts unchanged PAK file identity, builds the pinned CUE4Parse extractor, builds the graph, re-inspects original `NameProperty` and `FName` types in bounded packages, and runs the comparison. `trap` removes all temporary reports on exit.

### Interpreting results

- **Exact source value match:** only the serialized table contains identical public numbers. It does not prove identity because many rows may share a triplet.
- **Typed source row candidate:** an additional original saved class default `NameProperty` has an exact `FName` DataTable row key. This is more informative but still does not prove the class corresponds to the reference piece/tier.
- **No match:** investigate numeric representation, row inheritance, build divergence, different source tables or modifiers; *do not overwrite FoxBunker's validated data or fabricate row identities*.
- **Multiple matches:** inspect the class hierarchy, saved game references, variants and upgrade paths; don't prioritize by a guess based on similar file names.
- **Missing tier:** a nonbuildable tier in the reference. Never automatically convert `null` to zero HP.
- **Existing bot aliases:** 17 exact reference label aliases are recorded as an explicitly defined crosswalk. The bot key `radar` corresponds to reference **Interceptor Array**; FoxBunker's distinct **Radar** type is **not** the same row.

The output does **not** apply structural integrity compactness bonuses, infer faction, assign tiers by name, reconstruct UE runtime class defaults, compute breach/damage, or calculate wet-concrete modifiers. Those belong to subsequent independent, reviewed investigations.

## Follow-on investigation

For each typed candidate, trace class `SuperStruct`, saved upgrade/transform fields, owner `Structures/*` and expected individual bunker piece identity to resolve **type and tier** without guessed class names. Compare family/tier variants, record negative cases and obtain independent engine/native or user-confirmed evidence where needed. Keep raw game values and any full crosswalk in private scratch until publication is approved.

Run tests with:

```sh
python3 -m unittest discover -s test -p 'test_audit_foxbunker_structure_row_benchmark.py' -v
```

No upstream pulls, bot catalog changes, PAK mutation, Steam updates, merges or production writes are part of this workflow.
