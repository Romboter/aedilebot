# Foxhole game-file acquisition in GitHub Actions

This is **Phase 4 infrastructure**. It obtains the licensed game files and exports map JSON. It does **not** yet extract validated Relic Base names/sizes or automatically alter `Locations.csv`.

## Runner decision

GitHub's standard hosted Windows runners have **14 GB SSD**. Foxhole's current Windows game depot uses about **24.25 GiB installed**, including a roughly **23.9 GiB main PAK**, so a standard hosted runner is not suitable. A paid **150 GB Windows larger runner** could provide enough space, but Steam Guard authentication on ephemeral machines needs separate verification.

The current implementation targets a **dedicated, persistent Windows x64 self-hosted runner** with at least **80 GiB free** on its work volume (more is better). Assign it the custom label `foxhole-extract`. The runner must be isolated from unrelated/untrusted jobs; do not run arbitrary public PR code on a Steam-authenticated runner.

Official docs: [self-hosted Windows runners](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners) and [larger-runner sizes](https://docs.github.com/en/actions/reference/runners/larger-runners).

## One-time runner setup

1. Install and configure the GitHub Actions Windows runner (label `foxhole-extract`). Use a dedicated Windows identity for the runner service/process.
2. Install SteamCMD on this runner and use a Steam account that owns Foxhole. Complete initial Steam Guard verification **interactively using the SAME Windows identity that runs the GitHub job**. Keep SteamCMD's login/session data on persistent storage. This workflow deliberately accepts no password or Steam Guard code.
3. In the GitHub repository, create an environment called `foxhole-extraction` and set these **non-secret** environment variables (replace the example paths):
   - `FOXHOLE_WORK_ROOT` = `D:\FoxholeExtractor` (persistent volume, 80 GiB+ free)
   - `FOXHOLE_STEAMCMD_PATH` = `C:\steamcmd\steamcmd.exe`
   - `FOXHOLE_STEAM_USER` = your Steam login name
4. Ensure `git` is installed. The workflow installs Python 3.12 and .NET 10 SDK using GitHub setup actions.
5. Test SteamCMD *locally under the runner identity* first, using `+force_install_dir`, `+login`, `+app_update 505460`, and `+quit`. Confirm it can update Foxhole without requesting Steam Guard again. Steam may revoke the session, in which case an administrator must reauthorize locally.

The workflow is **manual only** until validated. Its extract job will queue until a runner with the required labels exists.

## Pipeline

1. `SteamCMD +app_update 505460` uses the preauthenticated Steam account to install/update `<work-root>/game`.
2. Check the expected `War/Content/Paks/War-WindowsNoEditor.pak` exists and is plausibly sized, and require SteamCMD's success message (never silently trust old game files).
3. Clone/update and pin [Tsekho/fh_map_exporter](https://github.com/Tsekho/fh_map_exporter) to SHA `db11ab571a6c95fb63c53d7c3bdec44d9f7966d1`; initialize its CUE4Parse submodules and build `Exporter.exe` from source using .NET 10.
4. Export maps headlessly: `Exporter.exe -i <game.pak> -o <work-root>/export`. Do **not** pass `-t`: terrain textures are unnecessary for Relic Base discovery.
5. Validate all `_json/*.json` maps using `inventory.py`; record per-map SHA-256, blueprint candidate counts and changes from last run.
6. Upload only `map-inventory.json` and `map-inventory.csv` as GitHub artifacts. **Do not upload game PAK files or raw exported asset JSON to the public repository.**

Exported map JSON remains locally on the runner at `<work-root>/export/_json/`. The inventory is diagnostic, not a production location catalog.

## Blockers before fully unattended/scheduled production operation

- **Schema:** The recovered `extract_relicbase_locations.py` expects original UnrealExporter/ArrowComponent JSON. The pinned CUE4Parse exporter writes a different `blueprints` dictionary, and its serializer can skip actors without mesh-bearing child components. Test against known Lykos Isle, Acrithia and Basin Sionnach placements; if Relic Bases are absent, modify the exporter to emit **all relevant actor transforms**, rather than reporting no relics.
- **Match names:** Use the appropriate War API static marker names *for each hex*, not the old batch script's one hardcoded marker list. Explicitly mark untrusted matches and missing size classifications (issues #15, #17).
- **Steam session:** First login and occasional Steam Guard reauthentication cannot be promised unattended. A dedicated preauthenticated runner is the initial strategy; validate repeated successful runs.
- **Scheduling:** GitHub Actions `workflow_dispatch` and `schedule` workflows require the workflow file on the repository's **default branch**. This repository's default is currently `main`, while the TypeScript rewrite lives on `rewrite/node-ts`. This feature PR alone does not activate manual/scheduled extraction. After review, a small matching workflow entrypoint must also be put on `main`, or the repository's default branch must change as part of the TypeScript cutover. Don't change the default branch simply to activate this pipeline.
- **Approvals and publication:** The tool does not edit or commit `Locations.csv`. The Phase 4 review engine will be a separate step.

To validate the safe inventory logic without Steam or a licensed game installation:

```bash
python -m unittest discover -s tools/map-extraction -p 'test_*.py' -v
```

## Dependencies
Issues #38 (acquisition/export), #14 (recover/adapt original extractor), #15 (War API), #17 (relic location matching), #13 (static source-of-truth).