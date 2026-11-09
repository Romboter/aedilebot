# Runbook: Audit AedileBot game data against a licensed Foxhole PAK

**Status:** First read-only real-PAK comparison validated on 2026-11-01; no production data updates or schedule implemented.

## Goal

Compare current `data/{Damage,Targets,Weapons,Bunker_piece}.json` against CUE4Parse DataTable exports from the **vanilla** Foxhole Windows PAK. Surface reviewable discrepancies while preserving manual aliases, ambiguous weapon data and bot behavior. Never automatically rewrite or merge bot data.

Use the private `Romboter/foxhole-lab` self-hosted Actions runner, NOT a public-repo self-hosted runner. The runner account `foxrunner` has read access to only the specific PAK file; `steamfetch` owns the Steam account and login state. The workflow creates a temporary directory with a symlink to that PAK so CUE4Parse can enumerate it without listing `steamfetch` directories.

## Inputs and commands

- Source extractor: `tools/cue4parse-extractor/Program.cs`, CUE4Parse Git submodule pinned by PR #46.
- Read-only comparator: `tools/cue4parse-extractor/audit_game_data.py`.
- Human-review identity candidates: `data_manual/target_devname_review_proposals.json` (NOT automatic corrections).
- Existing weapon factor mapping: `data_manual/weapon_multipliers.json`, explicitly **not trusted** as a verified physical weapon/mount link (issue #44).
- The private workflow `automation/data-diff-audit` in `Romboter/foxhole-lab` checks out an **immutable AedileBot commit SHA**, runs unit tests, creates a temporary symlink, exports only `Blueprints/Data`, and compares locally.

Offline comparator invocation after a real DataTable extraction (paths are illustrative; raw exports stay private):

```bash
python3 tools/cue4parse-extractor/audit_game_data.py \
  --stats /PRIVATE/OUTPUT/stats \
  --data data \
  --overlay data_manual/weapon_multipliers.json \
  --target-proposals data_manual/target_devname_review_proposals.json \
  --output /PRIVATE/OUTPUT/audit-report
```

Outputs: `audit.json` (full structured findings) and `audit.md` (summary and selected examples). The workflow uploads **only those derived reports** as artifacts to the *private* automation repository (30-day retention) and deletes transient raw exports. No PAK, raw tables, full maps, Steam credentials or bot write tokens are uploaded.

## What comparisons mean

| Audit section | Join | Checked | Not established |
|---|---|---|---|
| `damage_mitigation` | Damage profile ID | Sheet numeric mitigation fractions against `DTDamageProfiles` | Manual `Nomitigation` is not a game column; `TankZombie` absent from export |
| `vehicles_health` | `Dev Name` | `Targets.json` `Vehicles` HP vs `BPVehicleDynamicData.MaxHealth` | Emplacements, tripods, aircraft parts are not included |
| `structures_health` | `Dev Name` | `Targets.json` `Structures` HP vs `BPStructureDynamicData.MaxHealth` | A numeric mismatch may mean the wrong developer name, not a wrong HP value |
| `weapons_direct` | Ammo `Dev Name` | `BPAmmoDynamicData.Damage`, with the existing curated 1.25 kinetic factor | Any weapon in the unverified multiplier overlay is **not compared**, regardless of apparent numeric agreement |
| `bunker_tiers` | None | No authoritative tier-to-game-asset identity mapping yet | All 17 groups reported *not compared* |

A successful job only confirms the script ran and produced a report. **It does not assert that all game data agrees**. Unmapped rows, manually curated fields, and known source holes must remain visible. Do not fabricate joins from equal-valued multipliers or identical health values.

## Validated baseline — 2026-11-01

Private run: [41272950412](https://github.com/Romboter/foxhole-lab/actions/runs/41272950412), AedileBot comparator revision `e41d3380c09b10cf43c97b4aaf9a63edd49f0790`, vanilla PAK reported at 25,681,549,397 bytes.

| Section | Matched | Mismatched | Unmapped | Not compared |
|---|---:|---:|---:|---:|
| Damage mitigation | 342 | 0 | 1 | 0 |
| Vehicle health | 177 | 0 | 4 | 0 |
| Structure health | 242 | 10 | 9 | 0 |
| Weapon (direct only) | 55 | 0 | 9 | 43 |
| Bunker tiers | 0 | 0 | 0 | 17 |

The `Nomitigation` column has 20 manually maintained values in addition to the 342 matched source-backed mitigation values. `TankZombie` is the unmatched damage profile. Four unmatched vehicle rows: `OilTanker`, `SmallTrainEngine`, `SmallTrainDump`, `SmallTrainResourcePlatform`.

Eight of ten structure HP mismatches have an explicit **review candidate** with a developer-name row whose `MaxHealth` matches the sheet value. These are not automatically applied: Bridge, A0E-9 Rocket Platform Husk, Dry Dock, Dry Dock Husk, Offshore Platform, Infantry Support Gun Pillbox, Metalworks Factory Husk, Heavy Assembly Station Husk. The two remaining unmatched numerical differences are `RailTrackSplineFoundation` and `SmallRailTrackSplineFoundation` (sheet 750; DataTable 500). Investigation required before proposing changes.

Nine structure rows and nine weapon rows are missing source joins, and 43 weapon rows use an unverified multiplier mapping. Other categories intentionally excluded: `Aircraft_Parts` (40), `Emplacements` (24), `Multitier_structures` (7), `Tripods` (11). All 17 bunker tiers are unverified.

## Review protocol and release gates

1. Record the *current Steam build ID*, PAK file size/hash (or trusted manifest identity), exact extractor SHA, CUE4Parse submodule SHA and comparator SHA. The first pipeline stores the pinned tool SHA and PAK size but **does not yet capture a verified Steam build ID**; add before automated change detection.
2. Review all mismatched, unmapped and manually derived values. For candidate developer-name replacements, verify a real item/structure identity link, not merely a matching number.
3. Changes to target HP, aliases, armour mitigation or weapons must be made as **separate human-reviewed PRs**. Preserve manually curated fields. Verify calculator golden fixtures and `bot-ts` CI before merge.
4. Keep the private runner read-only to the public bot repo. A future GitHub-hosted job may open review PRs after extracting small approved derived data; it must not grant the PAK-reading VM public repo write credentials.
5. Never auto-merge. The bot must validate an approved data commit before any hot-swap and permit rollback.

## Tests

Run offline without Steam or PAK:

```bash
python3 -m unittest discover -s tools/cue4parse-extractor -p 'test_audit_game_data.py' -v
```

AedileBot CI tests this on GitHub-hosted runners. The private runner additionally tests against a real game file. Changes to the source tables, schema or mapping behavior should fail closed or produce a review finding, not silently overwrite data.

## Private provenance and version-to-version drift

The provenance recorder in `tools/cue4parse-extractor/record_audit_run.py` runs **after** an extracted DataTable audit succeeds. It computes:

- SHA-256 of the exact vanilla PAK, including a before/after inode, size and modification-time check to reject an archive that changed during hashing
- SHA-256 and byte size of each JSON DataTable output, with stable paths
- SHA-256 hashes of the four bot data sheets and both manual overlay files
- Exact AedileBot, CUE4Parse and private workflow commit SHAs
- Comparison counts and **only nonmatching, derived audit details**, not the raw DataTables
- Optional Steam build ID only when the specific Steam appmanifest is readable by the runner; otherwise `build_id: null` with an explicit unavailable status

The private workflow writes `provenance.json`, `drift.json` and `drift.md` alongside the current `audit.json` and `audit.md`. Only these five small **derived** reports go to the private repository's GitHub Actions artifacts. The per-run provenance snapshot is additionally stored on the isolated VM under `/home/foxrunner/.foxhole-audit-state/runs/<run-id>-<attempt>.json`. The last snapshot pointer is integrity-checked against SHA-256; missing or corrupt referenced history **fails closed**. This state contains no raw game assets and is not automatically removed.

The first run creates the baseline. Subsequent runs compare PAK hash, individual DataTable files, bot input files, tool revision pins and nonmatching findings; `changed_review_required` flags any drift. A clean audit of the same content reports `unchanged`. The report is **review only** even when all compared values match; no bot updates or merges are authorized by status alone.

### Scope and recovery

- Changing either source code or workflow SHA is a recorded implementation change, so it may create a review alert even with identical game data.
- Changing the PAK checksum requires review even if no checked stats change.
- A missing appmanifest **does not** prove the Steam build stayed the same. The PAK hash is the strongest observed artifact identity available under current ACLs.
- A malformed or missing `latest.json` target must not be silently treated as a new baseline. Restore the state from trusted private backup or explicitly review/reset the history through an operator-controlled process.
- If SteamCMD replaces the PAK, the file ACL may be lost; the human-operated ACL runbook in `Romboter/foxhole-lab` describes regrant and revocation.
- State is local to `foxhole-lab01` and is **not an independent backup**. Back it up outside the VM before relying on multi-month drift history.
- No schedule or unattended Steam login/update is enabled. The operator reviews a proposed game update before recalibrating the comparison.
