# Phase 4 (rework): Automated Game-Data Pipeline — Design

**Status:** DRAFT, mid-brainstorm. Not yet through the builder check; open items below.
**Date:** 2026-10-31
**Branch:** `rewrite/node-ts`
**Supersedes:** `2026-08-20-admin-data-pipeline-design.md` (Discord review flow, War-API
town polling, Steam PICS watcher). Kept for history; not yet edited to point here.
**Depends on:** Phase 3 hot-swap (`PluginHost<DataSnapshot>`, `data/dataStore.ts`).

Provenance key: **[User]** = decided by the user. **[Call]** = my default, not yet
agreed. **[Measured]** = measured in this session's spikes.

## Intent

After a Foxhole patch, game data in this repo should update itself: a build change is
detected, the game is extracted on a private runner, a PR with the changed data is opened
against the public repo, a human reviews and merges it, and the live bot picks up the
merged data with no restart. **[User]** "Something like SteamDB... a pipeline just
launches and a PR is made to approve to production." **[User]** "Fully automated, no more
by hand" — all of `Locations.csv`, `Weapons.json`, `Targets.json`, `Damage.json`,
`Bunker_piece.json`.

## Goals / non-goals

Goals: detect a new build within about 5 minutes; produce reviewable data PRs without a
human running tools; keep game files and Steam credentials off the public repo; bot
applies merged data safely (validated, rollback-able).

Non-goals / anti-goals:
- Raw game files, raw map JSON, or PAK contents in the public repo or in public artifacts.
- Any path that writes to the public repo from the extraction machine.
- Auto-merge. A human approves the PR. **[User]**
- Anything that can take the live bot down from a bad merge (validation gates the swap).
- The Discord review flow (`/admin-data-poll|import|review|edit|approve|reject`),
  `steamWatcher`, `reviewStore`, `diffEngine` as designed in the 2026-08-20 spec. The PR
  diff replaces them. **[Call, user agreed to PR-based review]**

## Pipeline

```
GitHub cron (5 min, hosted runner, private repo)
  -> api.steamcmd.net/v1/info/505460  public-branch buildid
     fallback: anonymous steamcmd +app_info_print 505460 (verified working)
     both fail: open an issue
  -> compare with last-seen buildid (repo variable)            [Call: variable vs file]
  -> changed: record it, dispatch extraction workflow
Private runner (foxhole-extract), environment with required approvals
  -> download/update Foxhole (SteamCMD, forced windows platform), vanilla pak only
  -> extractor (our own small C# console app on CUE4Parse; see Extraction)
       stats: Blueprints/Data DataTables; locations: relic/town actors from 53 hex maps
  -> build data files (TypeScript/Python: Locations.csv, Weapons/Targets/Damage/Bunker_piece.json)
  -> upload ONLY the small derived files as a private artifact
Hosted runner (private repo), last job
  -> download artifact, open PR on the public repo (bot token / GitHub App)
Human reviews + merges PR
Bot (any host)
  -> polls data/ on main (ETag), stages, validates, dataHost.swap(), notifies admin channel
```

## Detection **[User: 5-minute delay accepted]**

- GitHub `schedule` cron, minimum 5 minutes, hosted runner, in the private repo, on its
  default branch. **[Measured]** `api.steamcmd.net` returns `buildid` 26058282 for the
  public branch (7.2 KB, ~0.4 s, no documented rate limits, open-source backend that polls
  Steam PICS every 5 s). Anonymous `steamcmd` returned the same `buildid`.
- Compare only the `public` branch; another branch reported an older buildid.
- A buildid change includes hotfixes with no numbered update. Label the PR with the Update
  number from `ISteamNews/GetNewsForApp` (appid 505460) when one exists. **[Call]**
- GitHub disables schedules after 60 days of repo inactivity; the pipeline's own commits
  keep it alive. A queued job fails if the runner is offline for 24 h.

## Private runner **[User: private runner, ephemeral where it fits]**

- Separate private repo holds the workflow. The public repo is never attached to the
  authenticated runner (public-repo PR code would otherwise run next to the Steam session).
  Per `docs/runbooks/private-actions-runner.md` and `extraction-host.md`.
- Runner = disposable container (`EPHEMERAL=true`, `restart: always`, one replica, no
  `docker.sock`, no `--privileged`, own Docker network). State lives in host volumes:
  the work root (game files, archive, ~50-60 GiB) and the SteamCMD session dir. **[Call]**
- Registration needs a repo-scoped fine-grained PAT or a GitHub App; one-time tokens
  expire too quickly for an ephemeral loop. **[Open: which]**
- `concurrency` group so two extraction runs never overlap.
- The workflow example lives on `origin/feat/38-steamcmd-map-export`
  (`tools/map-extraction/private-runner-workflow.example.yml`). Draft PR #39 referenced by
  the runbooks is closed and unrelated; the runbooks' PR #39 links are stale.

## Extraction

### Stats (`Weapons.json`, `Targets.json`, `Damage.json`, `Bunker_piece.json`)

Source: `War/Content/Blueprints/Data/*.json` DataTables, via luk-gg/UnrealExporter
(CUE4Parse; v1.1.2 in use locally, v2.0.0 released 2026-05-11 with renamed config keys).
**[Measured]** a `Blueprints/Data`-only export took about 1 s (53 files, 2.7 MB).

Verified against build 26058282:

| File | Source table | Result |
|---|---|---|
| `Damage.json` | `DTDamageProfiles` | 342/342 cells match; `TankZombie` row absent from export |
| `Targets.json` vehicles | `BPVehicleDynamicData` (`MaxHealth`) joined on `Dev Name` | 177/177 match |
| `Targets.json` structures | `BPStructureDynamicData` | 249/259 match; 10 mismatches (Bridge 4200 vs 3250, Dry Dock 4650 vs 2000, ...) uninvestigated |
| `Weapons.json` | `BPAmmoDynamicData` joined on `Dev Name` | 98/98 reproduced as ammo damage x kinetic 1.25 x weapon/mount `DamageMultiplier` (see open item 1) |
| `Bunker_piece.json` | `BPStructureDynamicData` | health tiers (1500/2500/3500, 750/2000/3750) present; join not built |

The earlier 17 vehicle mismatches were entirely a stale (April) export.

Always re-export stats (cheap) and diff the produced files; do not rely on size-only
checkpoints for these (a balance change usually keeps file size). **[Call]**

Names and aliases ("Additional Names", display names) are human-curated and never come
from the game. The pipeline updates numbers and preserves the curated columns, and flags
new items with no alias. **[Call]** Rows with a blank `Dev Name` (emplacements, some
tripods, train items; ~30 in `Targets.json`) need their dev name entered once by hand.
Fields not yet located in the export: weapon range, reload, disable-chance columns
(likely `BPWeaponDynamicData` / `BPMountDynamicData`; unchecked).

### Extractor decision **[User: C#; Call: own program rather than a wrapper]**

Write a small C# console app (a few hundred lines, .NET 10) that calls CUE4Parse directly.
It takes a pak path and output dir and writes small JSON; the rest of the pipeline
(diffing, file generation, PR) is TypeScript/Python. Rationale **[Measured]**:

- luk-gg/UnrealExporter is a thin CLI wrapper (config, regex paths, `Parallel.ForEach`,
  checkpoints). It serializes every export (27,792 in Acrithia; 3.3 GB across the hexes)
  to read ~8 actors. A direct program reads only the needed actors.
- Tsekho/fh_map_exporter spends 26 of 30.6 s per map exporting meshes (467 `.psk`, 111 MB)
  that we do not use; skipping that (local patch) gives 5.8 s with byte-identical JSON. It
  has no skip flag, no license file, and rebuilding it on current upstream CUE4Parse gave
  no speedup (5.9 s) and needed fixes for removed landscape/mesh APIs. Parsing itself is
  ~2 s of the 5.8 s, so a faster parser (e.g. a Rust rewrite) would not help.
- The raw luk-gg map export already contains the relic/town actors; positions from the
  root component's `RelativeLocation` are identical to Tsekho's for all 8 Acrithia
  structures (no parent attachment, so no transform math needed).
- Cost: we own a small project, CUE4Parse's API churns, native Oodle/zlib DLL setup must be
  copied from luk-gg's `ExportService.cs`, and Linux native libraries are unverified.
  Check CUE4Parse's and luk-gg's licenses before reusing setup code.

Location and dependency **[User]**: the extractor lives in this repo (suggested
`tools/game-extractor/`, own `.csproj`, path-filtered CI) and consumes CUE4Parse as a
**git submodule**, chosen so we can patch it later. (A pinned NuGet package
`CUE4Parse 1.2.2.202610` also exists; not chosen.) CUE4Parse and luk-gg/UnrealExporter are
Apache-2.0. **[Call]** Pin the submodule to a reviewed commit; init it non-recursively
(`git submodule update --init CUE4Parse`) to skip its nested native-code submodules (ACL,
catch2), since Tsekho's build ran Acrithia fine with the native build failed (no `cmake`);
if a patch is needed, fork CUE4Parse and repoint the submodule URL then. The repo has no
submodules today, so CI and runner checkout must fetch it (`submodules: true` on the
`actions/checkout` step in the private workflow).

**[Measured]** throwaway spike (`D:\work\extractor_spike`, ~60 lines, project-referencing
CUE4Parse upstream HEAD, single process, Windows, warm cache): `AcrithiaHex` in 2.6 s
(8 structures); 52 hexes in 83.6 s total (~1.6 s/map), counts identical to the
luk-gg-raw-export-derived counts for every hex. `Maps/Master` also has a non-`*Hex` map
(`MarbanHollow`), so list every `.umap` directly under `Maps/Master/` (not `Proxies`)
instead of matching `*Hex`. Linux not yet run.

**[Measured]** the same spike's `stats` mode dumped all 53 `Blueprints/Data` assets in 0.67 s.
Versus luk-gg's (older bundled CUE4Parse) output of the same pak: 26 tables identical once
the new `Flags`/`Package` keys are ignored, including `DTDamageProfiles`, `DTArmourProfiles`,
`BPAmmoDynamicData`, `BPStructureDynamicData`, `BPMountDynamicData`. Real value differences
only in `BPVehicleDynamicData` (`VehicleSubsystemDisableChances` 61 rows,
`VehicleSubsystemRepairCost` 2 rows; new parser emits indexed entries with values where the
old gave `None`, which also fixes the duplicate-key problem) and `BPWeaponDynamicData`
(`MovementData`, all 57 rows, e.g. Mortar TurnRateScale 0.5/WalkingSpeedScale 0.3 vs 0.6/0.6).
Which parse is correct for those fields is unverified; the fields the sheets use today
(damage, MaxHealth, damage multipliers) are identical under both. Consequence: pin the
CUE4Parse commit and diff against a stored baseline so parser upgrades show as data changes.
The Targets/Damage/Weapons comparisons give the same results from this extractor's output as
from luk-gg's (vehicles 177/177, Damage 342/342, structures 249/259, weapons 43/98).

Oodle/zlib on Linux **[Measured on Windows, Linux not run]**: Foxhole's pak (v8, 25.7 GB)
lists no compression methods in its footer, so it appears uncompressed; neither
exporter's output folder contains an Oodle or zlib-ng library after running, so none was
needed for the maps/blueprints we read. If a future patch compresses the pak, CUE4Parse
(`OodleHelper.cs`, `ZlibHelper.cs`) downloads `liboodle-data-shared.so` (OodleUE
`gcc-x64-release.zip`) and `libz-ng.so` (Zlib-ng.NET) from GitHub at first use on Linux;
the pipeline should call the helpers' `Initialize(path)` with a pre-fetched, pinned copy
instead of a runtime download, and fail loudly if decompression is "not initialized".
Textures/landscape (SkiaSharp) and animations (`CUE4Parse-Natives`) are not used.

### Locations (`Locations.csv`)

Source: placed actors in each hex's `.umap` (`War/Content/Maps/Master/*Hex`; skip the 260
`Proxies` maps). Duplicate actors at identical coordinates collapse to one (Acrithia has
two `BPTownBase3_C` at the same position). **[Measured]** for `AcrithiaHex`: `BPRelicBase1/2/3_C` (exported as `BPDestroyedRelicBase*`) and `BPTownBase1/2/3_C` are present; nearest
War-API `mapTextItems` marker (world->API: `x = 0.5 + wx/218400`, `y = 0.5 + wy/189000`,
reproduces the old spec's reference point to 7 decimals) gave the right named location
for all 8 structures, and the tier -> type mapping against `Locations.csv` was:
RelicBase1/2/3 = Small/Medium/Large Relic; TownBase1/2/3 = Post Office / School / Town
Center. Confirmed in detail for one hex. Across all 53 hexes, per-type counts from the
export match `Locations.csv` in 41 hexes and differ in 12 (17 type-counts, e.g. Howl County
Large 1 vs 2 / Medium 2 vs 1, The Fingers Medium 3 vs 5, Stema Landing Medium 2 vs 0,
Weathered Expanse Post Office 4 vs 3); which side is right is not determined — these are
what a data PR should surface for review. `Locations.csv` mixes "Post Office"/"Post Office
TH" style labels (also School, Town Center) and six hexes are named differently from the
export (`THE MOORS`=`MooringCountyHex`, `LINN OF MERCY`=`LinnMercyHex`,
`THE HEARTLANDS`, `THE OARBREAKER ISLES`, `THE DROWNED VALE`, `THE GUTTER`); the pipeline
needs label normalization and a hex-name map. It makes the live-war-state noise problem
(old spec Risk #1) disappear: positions come from the pak, not `dynamic/public`, and relic
size no longer needs the War API (which collapsed all relics to tier 1).

Names still come from the War API `static` `mapTextItems` (nearest marker). Add a
distance cutoff to flag weak matches (one match was 0.0165 away vs 0.0001-0.003 typical).
CSV case differs from API text ("Thetus ring" vs "Thetus Ring"). **[Call]**

### Performance **[Measured]**

| Run | Time |
|---|---|
| luk-gg full (Blueprints + all 313 maps) | 593 s, 3.9 GB |
| luk-gg stats only | 1 s |
| Tsekho, one hex | 32 s (10.7 MB JSON) |
| 8 hexes, 1 / 2 / 4 / 8 parallel processes | 280 / 169 / 101 / 84-93 s |

- Hex maps are 3.3 GB of JSON in luk-gg's full export, proxies 651 MB; exporting only the
  53 hexes with luk-gg's tool was estimated at 7-9 min sequential (not run). 
- Parallel scaling (Tsekho's tool, 8 hexes, meshes on) is CPU-bound, not disk-bound (warm
  cache, ~0 MB/s reads): each process is multithreaded; 4 processes use ~48% of 24 cores,
  8 saturate. If we run several extractor processes, pool size ~ cores/3, configurable.
  Cold-cache behaviour on the runner is untested.
- Skipping unchanged maps is now low priority: with the direct extractor the full 53-map
  run is expected to be minutes. luk-gg's checkpoints compare path + size only (miss
  same-size edits), so do not rely on them. Revisit only if timing demands it. **[Call]**
- Exporter output has duplicate JSON keys (e.g. `VehicleSubsystemDisableChances`
  repeated); the stats parser must keep them (`object_pairs_hook`).
- Never point an exporter at `War/Content/Paks` (it contains mod paks and luk-gg's code
  has `TODO: Ignore mods`). Use a clean directory containing only the vanilla pak
  (hardlink worked). **[Measured]**

## Delivery: PR to the public repo **[User: option 2]**

- Last job runs on a GitHub-hosted runner, downloads the small-file artifact, and opens a
  PR using a bot token or GitHub App scoped to the public repo. The extraction machine
  holds no public-repo write credential.
- PR contains only `data/*` changes plus a summary (buildid, Update number, counts of
  changed rows per file, weak-match flags). A human merges. **[User]**

## Bot ingestion **[User: picks up new data on its own; admin notifications yes]**

- Poll `data/` on `main` every few minutes with `ETag`/`If-None-Match` (public repo, no
  credentials). **[Call]**
- Track the last applied commit. On a difference: stage the files, run the existing
  loader validation (Phase 3 `PluginHost` path), write to the data dir, `dataHost.swap()`.
  Validation failure leaves live data untouched; retry on every poll (not only on the next
  change) with backoff (e.g. 5 min -> 1 h), alert once. Transient network errors retry at
  the normal rate with no alert unless prolonged. **[Call, user corrected my "next change"
  wording]**
- Post to an admin channel on a successful swap and on a validation failure (once).
  Channel ID via env var, matching `TEST_GUILD_ID`'s pattern in `config/env.ts`. **[User:
  yes to notifications; Call: env var]**
- Runs under AMP in a Linux container (outbound-only network assumed). **[Call]**

## Open items

1. Weapon damage multiplier **[Resolved; Measured]**. Sheet damage = `BPAmmoDynamicData.Damage`
   x kinetic factor x the firing weapon/mount `DamageMultiplier` (`BPWeaponDynamicData` /
   `BPMountDynamicData`), reproducing 98/98 `Weapons.json` rows that have an ammo row.
   - Variant labels are the same multiplier: "(+20% HV)" = 1.2, "(+25% HV)" = 1.25,
     "(-33% LV)" = 0.66 (HV/LV = high/low velocity); the label is only a cross-check.
   - Kinetic factor 1.25 applies to every ammo whose damage type contains "Kinetic"
     (`LightKinetic`, `HeavyKinetic`, `AntiTankKinetic`, `LightKineticInfantryMine`) plus
     `AircraftAmmo` (Shrapnel, direct hit); all other ammo is x1.0. It is in no exported table
     (all 34 `Blueprints/DamageTypes` classes checked), so it is a constant in the generator.
   - Not in the assets: which weapon/mount row a sheet entry fires from (weapon->ammo link is
     native). Kept as a hand overlay, `data_manual/weapon_multipliers.json`, seeded from the
     sheet; equal-valued rows are interchangeable. Rows with no ammo row (garrison, AI shells,
     ATG, pillbox) stay hand-entered.
   - The M925 Austringer torpedo's 2458 is a transposition of 2485 (3550 x 0.7); the generator
     emits 2485.
   - Generator: `scripts/gen_weapons.py STATS_DIR [--seed|--write]`; without flags it prints
     drift and exits 1 if the sheet differs from the export.
   Other history (upstream issue #9): sheet values are calibrated to observed in-game damage.
   Worked case (upstream issue #9, Mammon 91-b = `HEGrenade` 240 Explosive vs Watchtower
   350 HP). NOTE `Damage.json` / `DTDamageProfiles` values are MITIGATION fractions: the
   calculator does `damage * (1 - value)` (`calculateDamage`). Explosive vs `Tier1Structure`
   = 0.25 -> 180/hit -> 2 hits (bot output today: "2 to 3 Mammon 91-b to kill a Watchtower",
   run through the real calculator), observed 3 in game (user: Watchtower unchanged since
   2023, still 3). So the real per-hit factor f vs the nominal 180 must satisfy
   2*180*f < 350 (f < 0.972; the RPG/Rifle Pillbox example gives f < 0.970): the 0.95/0.94
   "low roll" is one value in that range, not derivable from assets (no damage
   roll/variance property exists in any exported table or blueprint; no `ScriptBytecode` is
   exported; the logic is native). (An earlier draft of this note misread the values as
   multipliers and claimed a u59 change 0.75 -> 0.25 and "6-7 grenades"; both were wrong:
   no evidence of such a change was found, and 0.25 already appears in the 2023 sheet.)
   The Watchtower's armour type is still unverifiable from assets: `BPWatchTower` has no
   `ArmourType`; 67 of 254 structure rows in `Targets.json` have
   none in their blueprint (sheet types for these come from elsewhere; the 186 that do match
   the sheet except 1: `RailTrackSplineFoundation`). Chased through parent classes: of the 67,
   22 inherit an `ArmourType` from a parent blueprint (21 match the sheet; 1 differs,
   `SmallRailTrackSplineFoundation`), and 45 derive it from a native C++ base class (e.g.
   `WatchTower`, `Keep`, `Factory`, `Hospital`) so the type is not in any exported asset. The
   sheet is right on 207 of 209 verifiable rows, so its native-class types (incl. Watchtower =
   Tier1Structure) are probably right but unverifiable from assets: the pipeline should carry
   them as a hand-maintained overlay (keyed by Dev Name), verify the 209 it can, and flag new
   structures with no resolvable `ArmourType`.
   Native source trace: `Modding/Tools/Foxhole-Template-master.zip` (2022-10-19, UE 4.24)
   contains a generated `Source/War` module (1,298 headers, 1,085 .cpp) with constructor
   default values, but no gameplay logic (functions are empty stubs). `AStructure::AStructure`
   sets `ArmourType = EArmourType::NoArmour`; no other native structure class (including
   `AWatchTower`, `AKeep`, ...) sets it, and `BPWatchTower` doesn't override it, so by assets
   the Watchtower's armour type is `NoArmour`, not the sheet's `Tier1Structure`. The same
   holds for the 45 native-derived structures (e.g. `Factory`, `Keep` = `Tier3Structure` in
   the sheet), so something at runtime (not in the stubs, possibly newer than the 2022 snapshot)
   must assign the real type. `DTDamageProfiles` has no `NoArmour` column (the sheet's own
   `Nomitigation`/"-" column covers 3 rows). Resolving this needs either an in-game test or
   reverse-engineering `War-Win64-Shipping.exe` (80 MB; only enum names are visible in strings);
   not done, EULA not checked. Observed-behaviour check: with mitigation semantics, `NoArmour`
   (0 mitigation) would give 240/hit = 2 hits even at a 94% roll, contradicting the observed 3;
   `Tier1Structure` (0.25 mitigation = 180/hit, 3 on a low roll) fits, so the sheet's
   Watchtower = `Tier1Structure` is supported by behaviour and the runtime must assign it.
   Derivation test **[Measured]** (can armour type be derived from the data, no hand input?):
   among the 209 structures whose type is readable, no single exported feature predicts it
   (majority-class baseline 36%; `ProfileType` 61%, MaxHealth 74% but by memorising 41
   distinct values; the only 100% features are identifiers). Sibling rule "same native base
   class -> same type", leave-one-out on the 209: correct 110 of 186 (59%); applied to the
   45 it has a known sibling for only 4 of them and agrees with the sheet on 0 of those 4.
   Conclusion: the 45 native-class structures' armour types cannot be derived from game
   data; they stay a hand-maintained overlay (seeded from the current sheet, which is 207/209
   on the verifiable rows), and the pipeline flags any new structure not in the overlay.
2. 10 structure-health mismatches **[Resolved]**: 8 are wrong `Dev Name`s in `Targets.json`
   (the sheet's value equals the export's `MaxHealth` of a different row): Bridge ->
   `DrawbridgeB` (4200), A0E-9 Rocket Platform Husk -> `RocketSiteDestroyed` (5400), Dry Dock
   -> `FacilityVehicleFactory3` (4650), Dry Dock Husk -> `FacilityVehicleFactory3Destroyed`
   (6375), Offshore Platform -> `FacilityMineOilRig` (1850), ISG Pillbox -> `ISGPillbox` (950),
   Metalworks Factory Husk -> `FacilityRefinery2Destroyed` (6000), Heavy Assembly Station Husk
   -> `FacilityVehicleFactory2Destroyed` (4050); fix the sheet's Dev Names (the pipeline join
   would otherwise read the wrong rows; the 3 Shipyard-family rows currently share `Shipyard`).
   2 are real value differences: `RailTrackSplineFoundation` and `SmallRailTrackSplineFoundation`
   (sheet 750 / Trench, export 500 / `Tier3BStructure`, same for the BP default); sheet likely
   stale or describing a different object.
3. Locate weapon range/reload and disable-chance columns in the export.
4. Verify tier -> type mappings on more than one hex (all 53); define the weak-match cutoff.
5. Build the direct CUE4Parse extractor (C#, user-approved): time it, verify it builds and
   runs on Linux (Oodle/zlib natives), check CUE4Parse/luk-gg licenses before reusing setup
   code, pin the CUE4Parse commit. Resolve the 12 hexes whose counts differ from the CSV
   (check against War API / in game).
6. PAT vs GitHub App for runner registration and the public-repo PR.
7. Repo variable vs committed file for last-seen buildid.
8. Cold-cache timing on the Ubuntu runner; its core count sets the pool size.
9. (Low priority) skipping unchanged maps; only if the direct extractor is slower than expected.
10. Steam: does the runner need a Steam account login to download the Windows depot
    (anonymous `app_info_print` works; downloading Foxhole is untested).
11. Old spec items still pending: its Risk #2/#3 (PICS watcher) are moot; Open item
    "Foxhole AppID" is resolved (505460).
12. Docs to update when built: `docs/STATUS.md` (issues #18-#20), `architecture.md`,
    runbooks `private-actions-runner`, `extraction-host`, `data-change`, `hot-swap`.

## Provenance of measurements

Spike scripts and outputs are outside the repo in `D:\work\fh_map_exporter_spike` and
`/tmp` (`match.py`, `bench.sh`, `diag.sh`, `sample.ps1`, comparison scripts). Fresh export
at `UnrealExporter-1.1.2/output/fresh` from a hardlinked vanilla pak
(`War/Content/fresh-b26058282`), build 26058282. Nothing in the repo's `data/` changed.
