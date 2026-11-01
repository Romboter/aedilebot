# Exact Structure.CodeName to BPStructureDynamicData source-row identity

## Why

The pinned Foxhole build `26058282` has `Data/BPStructureDynamicData` with **592 rows**, all exposing `MaxHealth`, `StructuralIntegrity`, `RepairCost`, `DecayStartHours`, and `DecayDurationHours` (restricted survey #41345485604). These are necessary inputs to the upstream bot's structure and bunker calculator, but the correct entity → row join and effective runtime value cannot be inferred from matching a display name.

## Source-only method

`scripts/audit_structure_dynamic_row_identity.py` reads the exact SHA-256-verified `Data/BPStructureDynamicData` asset and build-pinned index. For every `Structures/` generated class with a single saved default, it compares an **explicit** default `CodeName` declaration (already indexed in the source graph) with a DataTable row key using exact case-sensitive identity.

Original Unreal type evidence comes from a separate pinned extractor branch `research/83-structure-original-codename-tags`, which extends the existing source-tag inspector with `CodeName`. Its immutable commit is `ad4c97e4bfe719cc24e7e3bb238563d75f49d799`. The inspector checks original `CodeName` property tags and independently reports `UDataTable.RowMap` key type. A join is marked `original_nameproperty_and_fname_row` only when the source `CodeName` tag is `NameProperty`, the actual table key is `FName`, and the saved identifier exactly matches a row name. All other source matches remain type-unverified candidates, not promoted.

Every candidate preserves package hash, exact export, field, saved parent candidate, table hash, exact row, original type evidence and hashes/shapes for named structure row fields. Original numeric values remain in restricted scratch.

```bash
python3 -m scripts.index_blueprint_graph \
  --source-root "$ROOT" --build-id 26058282 \
  --output "$SCRATCH/index.json"

# Build exact manifest from the graph's explicitly saved
# Structures/* Default__ CodeName sources plus Data/BPStructureDynamicData.
dotnet run --no-build -c Release \
  --project extractor-src/tools/cue4parse-extractor/Extractor.csproj \
  -- "$SCRATCH/vanilla" "$SCRATCH/unused" inspect-types "$SCRATCH/manifest.txt" \
  > "$SCRATCH/original-types.log"

python3 -m scripts.audit_structure_dynamic_row_identity \
  --source-root "$ROOT" --index "$SCRATCH/index.json" \
  --inspector-log "$SCRATCH/original-types.log" \
  --inspector-commit ad4c97e4bfe719cc24e7e3bb238563d75f49d799 \
  --output "$SCRATCH/structure-rows.json"
```

Private runner workflow: `Romboter/foxhole-lab` branch `automation/structure-dynamic-row-identity`; file `.github/workflows/structure-dynamic-row-identity.yml`. The process pins the Steam build, dedicated runner identity, application commit and original-tag inspector commit, and removes exports on completion. Complete reports must remain private; logs print bounded names and counts only.

## What a join does **not** establish

Even a type-proven source `CodeName` → row relation does **not** show:

- That the specific structure is active/spawnable in the game
- That an omitted child `CodeName` is inherited, or that a parent row is selected
- That the runtime uses `MaxHealth`, `StructuralIntegrity` or `RepairCost` without modifiers
- That bunker size, tiers, green/red edges, shelter and wet-concrete rules have been independently reconstructed
- Damage mitigation matrix semantics or native `/Script/War` calculations

Cases with absent, malformed, missing or case-only row identifiers remain unresolved, without guessed matches. Reusing the same row across multiple classes is reported separately, never treated as an error or a unique entity identity.

Do not use this to generate automatic bot catalog changes or damage calculations; only a separately reviewed, effective-value validation can establish that capability.
