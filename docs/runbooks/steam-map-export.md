# Runbook: Download Foxhole and export every map on Ubuntu

**Status: DRAFT / NOT RUN AGAINST REAL GAME CONTENT.** Native C# exporter compile/launch was tested in CI; the complete licensed SteamCMD PAK download and map export are **not verified**. Source is in [draft PR #39](https://github.com/Romboter/aedilebot/pull/39). **Use for:** authorized extraction job and initial commissioning.

## Preflight

1. Work only on an isolated [extraction host](extraction-host.md), via a reviewed **private** workflow or an interactive test under the dedicated service account. Never run the private Steam account job in public-repo PR CI.
2. Confirm at least the planned free space, persistent archive volume, network access and **same-user Steam Guard login**. Do not pass Steam password or verification codes on the command line or in GitHub secrets.
3. Review/pin the exact exporter commit (draft uses db11ab571a6c95fb63c53d7c3bdec44d9f7966d1) and AedileBot PR source commit. The exporter is a third-party C#/.NET project that emits *processed* map JSON, not validated complete raw Unreal actor data.
4. Record game build identity if SteamCMD provides one reliably; current archive manifest leaves game_build_id null rather than inventing it.

## Manual SteamCMD bootstrap (run once interactively as the runner user)

~~~bash
/usr/games/steamcmd \
  +@sSteamCmdForcePlatformType windows \
  +force_install_dir /srv/foxhole-extract/game \
  +login YOUR_STEAM_USERNAME \
  +app_update 505460 \
  +quit
~~~

Enter Steam Guard credentials only in the secure interactive program flow. Confirm SteamCMD's success output and that War/Content/Paks/War-WindowsNoEditor.pak exists under the chosen install root. This command on Linux forces the Windows depot; it does not install/run the game via Wine.

## Automated run (only after provisioning)

1. In the **private** GitHub Actions repo, manually dispatch the reviewed workflow; its checkout must pin a reviewed AedileBot commit containing tools/map-extraction from PR #39. The public workflow runs only offline tests.
2. The script tools/map-extraction/steam_export.sh does the following in order:
   - use SteamCMD to update Foxhole AppID 505460, fail if it cannot confirm a successful update;
   - verify PAK presence/plausible file size;
   - fetch and checkout pinned fh_map_exporter source/submodules and compile native linux-x64 with .NET 10;
   - export all maps to work-root/export/_json (stale working output is discarded **before** export; private archive is separate);
   - validate JSON inventory, SHA-256, candidate blueprint counts and changed map list;
   - **archive every exported map** in private, versioned, compressed content-addressed storage, update latest only after complete run.
3. Download the **small inventory artifact only** (not raw PAK/maps). Check inventory map_count > 0, expected map naming/coverage, and source hash provenance. Do not label empty relic candidate counts as correct absence.
4. Cross-check a sample of known actor placements against historical raw exports before approving any location proposal.

## Success criteria

SteamCMD confirms current download; parser exports multiple correctly shaped maps; inventory matches source directory exactly; archive's run manifest includes **every** map, source hashes and exporter revision; restored spot-check hashes match; no prior archive snapshots lost. No automatic Locations.csv changes.

## Failures and rollback

- **Steam Guard / entitlement:** stop; locally authenticate. Do not weaken private workflow security or log Steam credentials.
- **Missing PAK / depot mismatch:** stop and check platform override, Steam ownership and actual game directory. No stale fallback accepted.
- **Exporter build failure:** inspect exact .NET 10/runtime and pinned git submodules; don't download an unverified executable.
- **Missing structures:** source exporter may omit meshless actors; treat as **fidelity failure** (#40), not evidence relics were removed.
- **Disk full:** stop job. Preserve private archive; clear only an inspected, non-running work/export scratch directory through approved maintenance, never archive/blobs.
- **Partial run:** do not publish derived data. The historical archive/latest must still point to the last complete run.

**References:** [draft source](https://github.com/Romboter/aedilebot/pull/39), [archive runbook](map-archive-restore.md), [troubleshooting](map-troubleshooting.md).
