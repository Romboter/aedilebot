# Runbook: Preserve, verify, and restore complete map JSON archives

**Status:** Implemented in **unmerged PR #39**, tested with synthetic JSON; no production archives exist as a verified claim. Latest draft uses Zstandard level 15. **Use for:** recover historical per-map data, audit archive integrity, plan backups.

## Archive contract

Working export is disposable (work-root/export/_json). The private archive is **not**:

~~~
archive/
  blobs/sha256/ab/abcdef...json.zst     # exact compressed bytes of exporter JSON
  runs/2026...-runid-...json            # immutable per-run manifest
  latest.json                           # latest fully completed run pointer
~~~

Manifest records source format (fh_map_exporter-processed-json-v1), **full_actor_property_coverage_verified=false**, PAK SHA-256, exporter SHA, every map's uncompressed SHA-256 and size, and compressed blob path. Unchanged maps share a single blob across many run manifests.

**Critical:** “every map JSON” means every byte the current exporter emitted. It is **not proven complete Unreal actor/property fidelity** until #40. Keep processed and future raw full-fidelity formats distinct and versioned.

## Read-only verification (private host)

1. Read archive/latest.json and follow its run_manifest. Do not assume most recent filename is latest; a partial or unsuccessful run must not change latest.
2. Compare number of map records with map_count and actual inventory of that run. Confirm each blob is present. Example restoration of an **individual reviewed** blob:
   ~~~bash
   zstd -dc /srv/foxhole-extract/archive/blobs/sha256/ab/REPLACE_SHA.json.zst > /tmp/restored-map.json
   sha256sum /tmp/restored-map.json
   ~~~
   The reported hash must equal the full 64-character SHA from the manifest. Never infer a SHA from a map name.
3. Repeating restore on several changed/unchanged maps confirms exact-byte recovery. For automated verification use the archive tool's streamed checksum logic or a dedicated verification script, rather than loading all map exports in RAM.

## Backup and offsite copy

- Maintain private, access-controlled **off-host** backup of archive/blobs, archive/runs and latest.json. The archive includes derived game assets: do not put it in this public repository or public CI artifacts.
- Include manifest and required blobs in one coherent backup checkpoint. For long-running jobs, acquire backup during a known idle window or use a filesystem snapshot so latest and blobs are consistent.
- Record how restore is tested and what identity may access the archive; consider encryption at rest and capacity monitoring.
- No automatic retention/pruning is implemented. Do not delete old blobs just because latest points somewhere else: older manifests can reference them.

## Disaster recovery

1. Stop extraction/archival jobs; do not overwrite a partially recovered archive.
2. Restore archive to a **new empty private directory**; restore manifests and blobs together.
3. Validate latest.json points at an existing manifest; validate all referenced hashes on a representative sample (ideally all).
4. Use recovered source-format records to feed the matching parser; do not treat processed JSON as raw complete Unreal data.
5. Only after validation, redirect jobs to restored archive, keeping the damaged original read-only for forensic comparison.

## Historical gzip

Earlier development may have created .json.gz blobs. They are **not** deleted or transparently migrated; restore with gzip -dc if present. Latest implementation writes .json.zst. Do not rename a gzip file to .zst or assume a decompressor can read both.

**Sources:** [PR #39](https://github.com/Romboter/aedilebot/pull/39), [full-fidelity gap #40](https://github.com/Romboter/aedilebot/issues/40).
