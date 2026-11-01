# Runbook: whole-build serialized MultiAmmo audit

**Scope:** Read-only, source-backed declaration coverage on an authorized Foxhole PAK.
This is not runtime CDO reconstruction, weapon-damage computation, scheduling,
automatic approval, game downloading, production activation, or publication.

## Why

Issue #62 identifies four partial or empty child `MultiAmmo` declarations.
A hand-maintained list is insufficient for future Foxhole builds: new variants
could serialize the same way without being found by a targeted exception triage.
`scripts/audit_multi_ammo_declarations.py` discovers every explicitly
serialized class-default `MultiAmmo` via `index_blueprint_graph`, then
validates each package against the graph SHA-256 and follows its exact
`SuperStruct` chain.

It classifies each saved component declaration, records which serialized
nested field is defined on the target versus only on an ancestor, and
identifies a parent **candidate** where a child declares an incomplete or
empty compatible ammo list. Source package names, source hashes, and saved
field names are retained for review. The report intentionally does not
publish raw integer slot filters, reconstruct engine runtime defaults, or
promote a parent candidate to selected ammunition.

## Local commands (already extracted authorized PAK)

```bash
python3 -m scripts.index_blueprint_graph \
  --source-root /PRIVATE/extracted/War/Content/Blueprints \
  --build-id 26058282 --output /PRIVATE/index.json

python3 -m scripts.audit_multi_ammo_declarations \
  --source-root /PRIVATE/extracted/War/Content/Blueprints \
  --index /PRIVATE/index.json --output /PRIVATE/audit.json

python3 -m unittest discover -s test -p 'test_audit_multi_ammo_declarations.py' -v
```

Use the private workflow on `Romboter/foxhole-lab` for the real PAK. The
workflow must pin the exact `aedilebot` commit and assert the source build
before running. Only aggregated counts and small derived review summaries
may go to the GitHub Actions job summary.

## Output and interpretation

- `explicit_multi_ammo_cdo_packages`: number of package defaults with a saved
  `MultiAmmo` property found through the graph's declaration references.
  This does **not** include classes with wholly inherited, unsaved structs.
- `partially_serialized_struct`: saved structs without a
  `CompatibleAmmoNames` JSON list, including filter-only child structs.
- `partial_with_parent_candidate`: incomplete child saved struct with at
  least one explicitly saved ancestor name list. This **does not prove**
  actual inherited runtime ammunition.
- `incomplete_or_empty_with_parent_candidate`: either partial or explicitly
  empty child with an ancestor's separately saved options.

Every declaration emits `effective_at_runtime=not_established`. The source
record is only a serialized relationship inventory. Epic documentation on
Blueprint delta serialization and related struct/array caveats is useful
context but does not substitute for an independent UE4.24 runtime fixture.

## Failure behavior and future comparison

The tool rejects missing indexed files, changed SHA-256, broken parent links,
inheritance cycles, and malformed expected CDO records. It does not silently
repair case spelling or select a fallback weapon. Future build review should
compare both aggregate counts and per-source identities/SHAs, and surface
new partial/empty declarations for human assessment.

Never upload raw Foxhole PAK JSON, enable SteamCMD scheduling, auto-merge,
write production data, or activate calculated values from this inventory.

Related: [inheritance exception triage](inheritance-exception-triage.md),
[Blueprint graph indexing](blueprint-build-graph.md),
[Issue #62](https://github.com/Romboter/aedilebot/issues/62).
