# Runbook: Back up and restore AedileBot state

**Status:** Manual procedures; no production backup job or RPO/RTO has been verified. **Use for:** before release, patch, server move, disaster recovery exercise.

## Identify and classify source data

- **Public Git sources:** reviewed source/fixtures; Git history is not a backup of runtime state.
- **Operational config:** bot dev/prod environment, Discord application settings, guild/operator allowlists, Docker/AMP unit definitions. Store secrets separately with restricted access.
- **Mutable runtime data:** deployed data/*.json and Locations.csv (may differ from checked-in copies).
- **Logs:** error_log.txt can contain queries; retain only as permitted by documented privacy policy.
- **Private extraction state:** SteamCMD authenticated account state, downloaded game PAKs, archive/blobs, archive/runs and latest.json; preserve backup/manifest consistency.

## Pre-change backup checklist

1. Identify real deployed paths and running instances; do not guess based on repository example. Capture repo SHA, image digest/AMP configuration and UTC date.
2. Stop writes to changed files or use filesystem snapshot. For private map archive, wait until no archive run is committing latest.json.
3. Copy reviewed data to a **restricted off-host location**. Example from the repository root for a development data snapshot (not the whole production backup):
   ~~~bash
   mkdir -p ../aedilebot-data-backup
   cp -a data/Targets.json data/Weapons.json data/Damage.json data/Bunker_piece.json data/Locations.csv ../aedilebot-data-backup/
   sha256sum ../aedilebot-data-backup/* 
   ~~~
   This is only useful if source checkout contains the deployed data version; verify against the real service data.
4. Back up service configuration by your existing management system; **never include plaintext tokens in public artifact uploads**.
5. For map archives, back up every manifest and all referenced blobs, not only latest.json. Transfer to private off-host storage; test decompression and SHA verification.
6. Record backup identifier, encryption/access controls, retention, location, responsible operator and restore test result privately.

## Restore drill (prefer isolated staging first)

1. Rebuild a clean service environment with a known-good source commit; confirm whether intended runtime is Python or Node. Do not launch a bot with production token until identity checks pass.
2. Restore the **exact** data files into a separate staging directory and compare SHA against backup manifest. Test JSON parse, CSV structure and calculator outputs offline.
3. Restore environment through approved secret store; never paste credentials into code or documentation.
4. For map archive: restore to a new empty private directory, validate latest/run manifest links, decompress several map blobs and verify against SHA-256 of original JSON.
5. Re-enable service only after startup tests and rollback decision; monitor for missing/duplicated commands.

## Failure actions

Unreadable backup, inconsistent manifest or unknown source SHA: stop restoration and retain existing working state. Do not replace known-good production data with untested backup files. If user data/credentials were exposed, follow [incident response](incident-response.md).

**Sources:** [data loader](../../bot-ts/src/data/loader.ts), [archive runbook](map-archive-restore.md), [release cutover](release-cutover.md).
