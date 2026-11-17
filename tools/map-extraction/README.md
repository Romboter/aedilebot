# Foxhole game-file acquisition — Linux-first GitHub Actions

The intended pipeline is **SteamCMD on Ubuntu → Windows Foxhole depot → native Linux CUE4Parse exporter → per-map JSON inventory**. This is extraction infrastructure only. It does **not** yet produce validated Relic Base/Town Base identities or update Locations.csv.

## Archival policy — preserve every map export for later analysis

**Requirement:** retain a complete JSON export for **every** map on **every** successful acquisition/export run; generate small relic/Town Base catalogs separately. Never replace the full source data with a filtered catalog.

Both acquisition scripts now run `archive_exports.py` after successful export and validation:

- `<work-root>/export/_json/<map>.json` is the *current working export*, regenerated each run.
- `<work-root>/archive/blobs/sha256/<prefix>/<sha256>.json.zst` stores exact, losslessly Zstandard-compressed exported JSON bytes (streaming level 15). Unchanged maps deduplicate across runs; a changed map gets an additional blob rather than overwriting history.
- `<work-root>/archive/runs/<timestamp>-<run-id>-<random>.json` is an immutable manifest for each successful run: all map names, source SHA-256, byte sizes, content-addressed blob paths, exporter SHA, and source PAK SHA-256.
- `<work-root>/archive/latest.json` identifies the last fully committed run. A failed/incomplete archive does **not** advance this pointer.
- Nothing in the archive directory is automatically deleted. Capacity monitoring and independent backups are the operator's responsibility; 80 GiB is only a starting allocation, not guaranteed lifetime capacity.
- Zstd level **15** is a starting point for high-ratio archival. Run compression benchmarks on the real map JSON before raising it; retaining data exactly is more important than achieving a specific ratio. Compression choice does not certify actor/property fidelity. Historical `.json.gz` archives, if any, are left untouched and can still be restored with gzip.

To restore one archived map:

```bash
zstd -dc /srv/foxhole-extract/archive/blobs/sha256/<prefix>/<sha256>.json.zst > restored-map.json
sha256sum restored-map.json
```

**Caution:** These are complete byte-for-byte copies of the *current exporter output*, not yet certified **full-fidelity Unreal actor/property exports**. The C# exporter currently filters/aggregates some objects. Issue #40 requires extending it to preserve every map actor, component, property, transform and unknown field in a separate versioned raw JSON format, and validating against the recovered original exports. The snapshot manifest deliberately marks `full_actor_property_coverage_verified: false` until that work succeeds.

The persistent archive contains large derived game assets and belongs **only in private storage**, never in the public GitHub repository or publicly accessible CI artifacts.

## What has been verified

A pinned version of [Tsekho/fh_map_exporter](https://github.com/Tsekho/fh_map_exporter) (commit `db11ab571a6c95fb63c53d7c3bdec44d9f7966d1`) **compiled and started natively on Linux x64** in [GitHub Actions run 41170904073](https://github.com/Romboter/aedilebot/actions/runs/41170904073). This project hardcodes `win-x64` in its .csproj but the Linux build works when publishing with `-r linux-x64 -p:RuntimeIdentifier=linux-x64`. The exporter runs without Wine or Proton.

SteamCMD supports `+@sSteamCmdForcePlatformType windows` to download Windows game depots from Linux. **We have not yet tested this with Foxhole and a licensed Steam account.** Foxhole uses Steam AppID 505460; SteamDB lists ~24.25 GiB installed data.

## Host choice and security

The original Windows proof-of-concept is retained as `Invoke-SteamExport.ps1`; the preferred pipeline is `steam_export.sh` on Ubuntu 24.04, running directly in Linux with Python 3.12, .NET 10 and SteamCMD.

**Important: Romboter/aedilebot is a PUBLIC GitHub repository.** GitHub advises against persistent self-hosted runners for public repositories. A runner with Steam authentication must **not** have unrestricted access to unrelated services, privileged container sockets or host credentials. Preferred production arrangement:

1. An isolated Ubuntu worker with one private working directory on existing storage; no separate disk or filesystem is required. Monitor at least the provisional 50–60 GiB free starting range (game/update/working data) and additional growth from archived map revisions.
2. A **private repository for the actual GitHub Actions runner/dispatch workflow** (not this public repository), restricted to trusted commits and operators; checkout this code at a pinned commit. Do not run public PRs on the private runner.
3. Use a dedicated non-root account and separate Steam account entitled to download Foxhole (where licensing allows). Complete Steam Guard login interactively under the same account that will run subsequent automated jobs.
4. Never mount `/var/run/docker.sock`, game-server data folders or host SSH keys into this environment. Keep only explicitly required output paths writable.

The public `.github/workflows/foxhole-map-extract.yml` now contains **only safe offline validation jobs** (inventory/archival tests, Bash/PowerShell syntax, and a native Linux exporter build). The real SteamCMD job belongs in the **separate private automation repository**, using the reviewed `private-runner-workflow.example.yml` template and an isolated authenticated runner. Never attach the persistent runner to this public repository.

## Installing prerequisites on a dedicated Ubuntu 24.04 environment

Ubuntu's SteamCMD package is 32-bit and located in `multiverse`. In the isolated Ubuntu environment:

```bash
sudo dpkg --add-architecture i386
sudo add-apt-repository -y multiverse
sudo apt-get update
sudo apt-get install -y steamcmd:i386 git python3 python3-venv zstd
```

Use the private runner's Python 3.12 environment (or a virtual environment) to install the pinned compressor with `python -m pip install -r tools/map-extraction/requirements.txt`; on Ubuntu the system Python may be externally managed, so install into a virtual environment or use the `actions/setup-python` interpreter provided by GitHub Actions.

Install .NET 10 SDK for Linux (or use GitHub `actions/setup-dotnet@v4` for a runner job). Confirm `/usr/games/steamcmd` is available. Keep the game install in a persistent writable directory; do **not** execute the pipeline as root.

Test downloading the **Windows** files using your own entitled Steam account:

```bash
/usr/games/steamcmd \
  +@sSteamCmdForcePlatformType windows \
  +force_install_dir /srv/foxhole-extract/game \
  +login YOUR_STEAM_USERNAME \
  +app_update 505460 \
  +quit
```

Complete Steam Guard authentication interactively once; whether reauthentication is required later depends on Steam's session behavior. Do not place the account password or authentication codes in workflow arguments, logs or repository secrets.

After setting `FOXHOLE_WORK_ROOT`, `FOXHOLE_STEAM_USER` and optionally `FOXHOLE_STEAMCMD_PATH`, the pinned `steam_export.sh` script performs the update, native `linux-x64` exporter build, headless export, and diagnostic inventory. It refuses to report success when SteamCMD did not confirm a current install. The optional Windows script remains available as a fallback only.

The complete exported JSON is retained in the private local archive, not uploaded to GitHub. Only `map-inventory.json` and `map-inventory.csv` are uploaded as action artifacts; **never publish the proprietary PAK or complete raw exported asset data to the public repository**.

## Remaining technical validation before production

- **Actual game export:** The Linux exporter has started, but the full Foxhole PAK extraction has **not** yet been executed. A Steam-authenticated host is needed.
- **Actor fidelity:** The pinned CUE4Parse exporter writes a `blueprints` dictionary, unlike the recovered UnrealExporter/ArrowComponent JSON. Its serializer can skip actors with no mesh-bearing children; if Relic Bases are absent, extend it to preserve raw Blueprint actors/transforms. An empty relic count does **not** mean there are no relics.
- **Location identification:** Integrate the correct War API static map markers for *each* hex, test world-coordinate conversion, and do not silently assign labels based on distant closest matches. Relic size tiers still need empirical validation (issues #14, #15, #17).
- **Update safety:** No automatic deletion or changes to `Locations.csv`; put any proposed changes through the Discord admin review pipeline.
- **Workflow activation:** The current default branch is `main`; GitHub schedules and workflow_dispatch have default-branch requirements. Use the private automation repo to control schedules rather than changing the public bot's default branch just for this pipeline.

## Local test without game content

```bash
python3 -m pip install -r tools/map-extraction/requirements.txt  # In venv or Actions Python
python3 -m unittest discover -s tools/map-extraction -p 'test_*.py' -v
bash -n tools/map-extraction/steam_export.sh
```

Related issues: #38 (SteamCMD/export), #40 (full-fidelity raw map exports), #14 (recovered raw extractor), #15 (War API), #17 (relic matching), #13 (static source-of-truth).
