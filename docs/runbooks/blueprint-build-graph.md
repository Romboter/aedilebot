# Runbook: indexed Blueprint source graph and patch drift

**Stage:** read-only research for Foxhole build `26058282`. This is not a
generator, merge gate, automatic updater, or authorization to publish data.
Game PAKs, raw Blueprint exports, and full graph-index snapshots remain private.

## What is indexed

The build-wide graph indexer (`scripts/index_blueprint_graph.py`) walks the
licensed exported Blueprint JSON packages and emits four distinct data sets:

| Index section | What it means |
|---|---|
| `packages[]` | Exported package identity, SHA-256, and exported object count |
| `object_references[]` | Explicit `SuperStruct`, `MountComponent`, `ItemComponentClass`, projectile, grenade-class and explosion-template `ObjectPath` edges, with exact defining package/record/field |
| `numeric_row_references[]` | Explicit `AmmoName`, `CompatibleAmmoCodeName`, `MultiAmmo`, `GrenadeMultiAmmo`, vehicle seat `MountCodeName` and aircraft `WeaponConfigs[]` fields, joined **only by exact identifier** to `BPAmmoDynamicData` or `BPMountDynamicData` |
| `declarations[]` | Explicit `CodeName` and `ExplosiveCodeName` declarations. Their target table is **not inferred**. |

Each edge carries its defining export file SHA-256. Object links distinguish
`exported` from `missing_export`. Named table links distinguish
`row_present`, `row_missing`, `table_unavailable`, and
`invalid_identifier`.

This is a **declaration inventory**, not flattened inheritance. A vehicle
child may override only some of its seat properties; consumers still need
to follow `SuperStruct` and apply source-aware base-to-derived overrides
as implemented in the per-family resolver. The graph does not infer RPG
aliases, projectile damage, or relationships from matching values.

### Read-only command

~~~bash
ROOT=/PRIVATE/EXPORT/War/Content/Blueprints

python3 -m scripts.index_blueprint_graph \
  --source-root "$ROOT" --build-id 26058282 \
  --output /PRIVATE/audit/graph-26058282.json

python3 -m scripts.diff_blueprint_graph \
  --before /PRIVATE/audit/graph-26058282.json \
  --after /PRIVATE/audit/graph-NEW_BUILD.json \
  --output /PRIVATE/audit/graph-review-diff.json
~~~

Use independently retained, build-pinned snapshots. Both scripts only read
their input game assets. They write their JSON report only to an explicitly
supplied path, not to `data/` or a bot runtime directory. Do not commit
private raw exports or full graph snapshots to the public repository.

## Patch detection contract

`scripts/diff_blueprint_graph.py` compares three independent dimensions:

1. **Reference drift:** new, removed, retargeted, or now-unresolved explicit
   package references; changes to named ammo/mount rows or row availability;
   newly declared/missing `CodeName` and `ExplosiveCodeName`.
2. **Source-content drift:** a package or DataTable SHA-256 changes, even if
   recognized identifiers and source edges are unchanged. A change in
   an *unindexed* property can alter gameplay; this must remain reviewable.
3. **Build transition:** a new Steam build ID triggers human review even if
   recognized references and file hashes are identical. Never silently mark
   a new build approved because a numeric value was unchanged.

The diff checks the relation digest and rejects duplicate identity keys.
The `relation_digest` is deterministic across reruns and excludes nonsemantic
JSON formatting. **It is not a game-source authenticity signature.** Retain
the pinned Steam manifest build, vanilla PAK checksum, exporter commit and
private archive checksums separately.

A changed or missing edge must **never** cause the resolver to choose a
similarly named or numerically equivalent target. Snapshot activation and
automatic PR creation are still disabled.

## Required gates before automatic game updates

- Confirm complete, bounded extraction for all *recognized* edge types;
  record unknown/native references separately, not as successful coverage.
- Reproduce a full-build index twice byte-for-byte; reject nondeterminism.
- Correlate graph identifiers with bot entry names in a **separate,
  explicitly reviewed display-name join**. Generic ship entries may
  represent different per-vehicle mounts.
- Test an old/new build comparison with deliberate graph edge removals,
  target changes, missing dynamic rows and changes to previously unindexed
  properties. Require human review in every case.
- Validate real-game calculator fixtures and manual kinetic/native factors;
  a joined DataTable row alone does not prove final combat damage.
- Complete independently retained audit-history backup/restore,
  review-PR validation, and atomic bot snapshot rollback.

## Safety

The private workflow `Romboter/foxhole-lab`, branch
`automation/blueprint-build-index-validation`, re-extracts its pinned local
build into an ephemeral restricted workspace and checks deterministic
repeatability, empty same-build diff, and status accounting. It does not
upload raw assets or graph JSON, nor alter the game files or bot.

The public CI uses only synthetic exports. Build history, Steam credentials
and proprietary assets must remain on the private runner/archive.

Related: [Blueprint connection model](blueprint-reference-model.md),
[infantry modes](infantry-firing-modes.md),
[exact extraction](exact-blueprint-extraction.md),
[asset-derived data contract](../superpowers/specs/2026-11-01-asset-derived-data-contract.md).

## Explain a specific vehicle or weapon chain

The build-wide index is useful for comparing releases, but an operator needs
to answer, "What exported path connects **this** Blueprint to its mounts and
ammunition?" The read-only `scripts/explain_blueprint_graph.py` command
performs a bounded breadth-first traversal of explicitly referenced packages.
It shows the source property and exact `ObjectPath` at each hop, the
corresponding source-file hashes, and named DataTable row statuses on every
reachable package.

~~~bash
python3 -m scripts.explain_blueprint_graph \
  --index /PRIVATE/audit/graph-26058282.json \
  --package Vehicles/LargeShips/DestroyerC/BPLargeShipDestroyerC \
  --max-depth 10 --max-nodes 250 \
  --output /PRIVATE/audit/destroyer-graph-explanation.json
~~~

The output's `packages[].source_path` shows one deterministic, shortest
reference path to each reachable package. Other routes can exist; inspect
`object_references[]` to see them all. Unexported targets and missing ammo
rows are separately listed under `gaps`, never substituted.

A depth cap yields `bounded_partial_explicit_graph` and counts skipped
edges. Exceeding the package-count cap fails; it does **not** silently call
the partial graph complete. Even
`explicit_graph_closure_for_recognized_edges` means only that the current
set of recognized exported links has no missing target. It does **not**
prove gameplay semantics, flatten inheritance, pair multi-ammunition
variants to projectiles, or authorize automatic publication.

## First private whole-build baseline (26058282)

The broad Blueprint extraction and deterministic index both succeeded on
the restricted private runner: [full-source validation
#41280079499](https://github.com/Romboter/foxhole-lab/actions/runs/41280079499).
A second private run reproduced the same counts and captured the PAK SHA-256.

| Observed count | Build 26058282 |
|---|---:|
| Exported Blueprint JSON packages | 4,203 |
| Explicit package reference edges in the supported field set | 879 |
| References whose target packages were exported | 879 |
| Named ammunition/mount row references | 591 |
| Exact matching DataTable rows | 573 |
| Missing named rows | 14 |
| Invalid source identifiers | 4 |
| Explicit CodeName / ExplosiveCodeName declarations (unscoped) | 981 |

Initial relation digest:
`5d8b6679cc213630e7253ec2e06f51b394d61b7fa59d9074ae72c72e6b1e088e`.

Pinned local vanilla PAK SHA-256:
`3f927753301f64082a63df96d59c0e10961ee1582b3ff9f2a0267fbf7e7f1e20`.

The full private runner exports **4,203** package JSON files, whereas
the earlier curated archived Blueprint research ZIP contained **3,795**.
Do not compare raw graph coverage numbers across these different export
scopes without normalizing which assets were included. The broader
export includes the previously absent `BPWaterStencilComponent`.

The first missing-row investigation list includes repeated `RPGAmmo`
declarations (already documented in [Issue #53](https://github.com/Romboter/aedilebot/issues/53)),
`BattleTankMachineGunner`, `FieldMortarGunner`,
`HalftrackMultiWGunner`, and a lowercase `lighttankammo` reference.
These are *declared source references*; an unmatched identifier is not
permission to substitute a similarly spelled entry. Case-only matches
may be reported as **unverified diagnostics only** and must not be
promoted to a source edge without evidence.

**Interpretation:** 879/879 means only that all **recognized explicit
object-package links in this extraction** point to an exported JSON
package. It does not mean that all Blueprint connections, native runtime
properties, damage formulas, or player-facing bot identities are resolved.
The 573/591 exact named-row joins are a separate metric, with remaining
identity exceptions requiring investigation.

Future builds must be compared using the same extractor revision, source
root scope, and graph schema. This is a **review baseline**, not a
production-ready numeric-data pipeline.
