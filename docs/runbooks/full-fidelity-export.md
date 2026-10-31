# Runbook: Develop and validate full-fidelity Unreal map JSON

**Status: PLANNED — issue #40.** No implementation currently proves complete actor/component/property coverage. The external CUE4Parse project builds and launches on Linux, but its processed output can omit placement-only actors. **Use for:** anyone improving the C# exporter, implementing new raw schema, or comparing a game patch to historical maps.

## Contract

Preserve **two distinct products** per map:

1. **Raw full-fidelity export:** all actor records, component relationships, properties (including unrecognized fields), stable object identity, native and global transforms, class and resource references. Include unsupported-field diagnostics rather than silently skipping records.
2. **Derived analysis:** known relic/Town Base records and validated map labels, independently regenerable from the raw export. Derived fields should never replace the raw JSON.

The current Tsekho/fh_map_exporter writes mesh-oriented blueprints/symbols/groups/splines JSON and may skip Blueprint actors without mesh children. Do not call that raw/lossless data. Keep its processed format identifier separate from a new raw schema.

## Development procedure

1. Start from a pinned reviewed exporter SHA and inspect its MapExporter.cs serialization path (especially SkipTypes, CreatedBy, child mesh filters and blueprint branch). Choose either a reviewed upstream contribution or a separately versioned fork; do not silently modify downloaded source on a runner without pinning a commit.
2. Develop on isolated/offline sample map data first. Recovered historical LykosIsleHex sample included five BPDestroyedRelicBase actors and three BPTownBase actor entries (two share coordinates). Treat these as regression fixtures for the *historical game build*, not permanent current counts. Acrithia and Basin Sionnach examples also exist outside GitHub and have not been placed in this public repo.
3. Specify raw JSON schema fields: source format and version, hex asset path, object name/outer/class, component parent, raw RelativeLocation/rotation/scale, resolved world transform and optional original property payload. Record serialization failures and property type variants.
4. Export one known map; compare **class instances and coordinates** against historical raw export and known War API static markers of that same hex. Confirm distinct actors survive deduplication. Never infer Small/Medium/Large relic tiers from unverified mesh suffixes.
5. Test one or more additional hexes and multiple versions. Record actor count/parse errors so a silent omission cannot be a green run. Evaluate memory and disk: output one map at a time and stream JSON instead of loading all regions into one giant object.
6. Validate raw JSON can be archived and restored byte-for-byte using Zstd, with a new source_format identifier and immutable run manifest. Only after covered should full_actor_property_coverage_verified become true, based on a documented audit.
7. Ensure derived catalog extraction consumes the raw data without mutating it and flags unrecognized actors and labels for review.

## Gate and rollback

**Pass:** known actor counts/transforms match the reference build, unknown properties are either represented or explicitly reported, every region exported, and no silent filtering. **Fail:** any fixture actor missing, unknown classes discarded, inconsistent transform or parser crash. Keep the old exporter pinned, preserve archived JSON and reject new catalog proposals. See issue #40 and [map troubleshooting](map-troubleshooting.md).

**References:** [draft exporter integration PR #39](https://github.com/Romboter/aedilebot/pull/39), [issue #40](https://github.com/Romboter/aedilebot/issues/40), [issue #17](https://github.com/Romboter/aedilebot/issues/17).
