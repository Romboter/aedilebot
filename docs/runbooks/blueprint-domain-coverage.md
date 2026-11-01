# Pinned Blueprint domain coverage inventory

This research-only tool inventories exported asset path buckets and missing serialized reference grammar before adding domain-specific graph resolvers. Its domain labels are **path-based**, not authoritative Foxhole gameplay classifications. An `Items/` package may contain a projectile, mount, weapon, or unrelated item; `other_path` is not a negative gameplay finding.

## Reproduce

In the restricted `foxhole-lab` runner workflow `automation/blueprint-domain-coverage`, verify `foxrunner`, the existing pinned build `26058282`, and immutable extractor/source commits. Re-extract to mode-0700 temporary scratch, then run:

```bash
python3 -m scripts.index_blueprint_graph \
  --source-root "$ROOT" --build-id 26058282 --output "$SCRATCH/index.json"

python3 -m scripts.audit_blueprint_domain_coverage \
  --source-root "$ROOT" --index "$SCRATCH/index.json" \
  --output "$SCRATCH/domain-coverage.json"
```

The tool verifies the relation digest, all indexed source object edges, and every exact package SHA-256 before reporting. Full JSON stays inside restricted scratch. The workflow prints only bounded aggregate counts and normalized candidate field-family examples, never raw exports. The caller must review report field examples locally before promoting **any** new edge grammar.

## Interpret the output

- `package_roots`, `domains`, `lexical_package_name_candidates`: discovery inventory, not object classes or spawnable combat entities.
- `export_types`, `component_types`, `saved_default_fields_by_domain`: source export shapes; a `Default__` export is not a proven effective runtime CDO.
- `indexed_exact` means a previously indexed `ObjectPath` matched an exact source occurrence, not that the edge participates in damage computation.
- `unindexed_blueprint` means an explicit serialized Blueprint-path-shaped reference remains outside graph handlers, NOT an automatically actionable gameplay edge. Most are engine internals.
- `structure_defense_candidate_fields` uses lexical hints only: identify class ownership, original property types and actual combat semantics independently.
- `indexed_exact_row_present_source_only` counts references with an exactly matching available dynamic row; it does not imply runtime ammo selection or multiplier application.
- Missing target packages, native class defaults, partial nested `MultiAmmo`, and runtime values remain unresolved.

## Next action after the inventory

Select a frequent, combat-relevant **unindexed** family in structure/defense or weapon-bearing packages, inspect exact exporting class/type and original Unreal tags, then implement a narrow typed resolver with synthetic negative cases, PAK validation and provenance. Do not broaden object-path indexing indiscriminately. Maintain separate source field presence, exact export identity, inherited-source candidates and independently demonstrated runtime values.

## Operational restrictions

No Steam updates, imports into production catalogs, unattended publication, bot updates or merges. All source files remain in temporary private scratch. No public artifacts contain PAK exports, complete graph or per-asset reports. Use a dedicated branch, draft PR, and exact run logs. Parallel curated-human-data work remains independent.

Known related work: #62 (UE4.24 partial MultiAmmo defaults), #65 (whole-source reference inventory), #75 (explicit component-template deltas), #77-#79 (seat/mount source provenance).
