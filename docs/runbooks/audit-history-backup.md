# Independent audit-history backup

**Status:** Manual, review-only safeguard. No schedule or automatic production writes.

The provenance recorder stores snapshots on `foxhole-lab01` in `/home/foxrunner/.foxhole-audit-state`. GitHub Actions artifacts alone are not sufficient as an independently retained backup; they expire. Backups must reside on a separately managed host or storage service with its own retention and access controls.

## Operator setup

Provision a **pre-mounted, independently administered backup filesystem** with restricted permissions. Mount and verify it out-of-band, and ensure its lifecycle does not depend on the Foxhole VM. The backup utility refuses destinations on the same filesystem, but a different filesystem may still be a virtual disk on the same host: **this check does not prove physical independence**.

As the authorized runner account, after verifying the independent mount and permissions:

```bash
python3 tools/cue4parse-extractor/backup_audit_history.py create \
  --state /home/foxrunner/.foxhole-audit-state \
  --destination /PATH/TO/INDEPENDENT/MOUNT/aedilebot-history \
  --backup-id manual-20261101-01

python3 tools/cue4parse-extractor/backup_audit_history.py verify \
  --backup /PATH/TO/INDEPENDENT/MOUNT/aedilebot-history/manual-20261101-01
```

The destination directory must already exist, be owned by the invoking account, and mode 0700. The utility refuses overwriting an existing backup ID. Backup files are 0600. It copies only derived run snapshots and the latest pointer, not the PAK or raw DataTables. A SHA-256 inventory is generated and verified after copying; symlinks, unexpected files, missing records, malformed history, and mismatched hashes fail closed.

## Restore drill and incident response

1. On the backup host, verify a selected snapshot with the `verify` command and independently verify storage retention and isolation.
2. Quiesce audit writes. Do **not** overwrite a healthy history or synthesize a fresh baseline to conceal missing state.
3. Restore the verified `runs/` and `latest.json` to a new restricted directory (0700 directories, 0600 files), retaining the original broken state for investigation.
4. Verify the restored latest pointer SHA-256 and snapshot identities via `verify` against the backed-up snapshot; independently compare restored byte hashes with the backup inventory.
5. Only after an operator approves the recovery should the provenance recorder be pointed to the restored directory. Run a manual read-only audit and inspect its drift report.

## Release gate

Before anyone enables a schedule: perform a real off-host backup, demonstrate restoration on a separate machine, document operator/retention/access arrangements, and verify an intentional corruption causes a failure. Automatic Steam downloads and production data updates remain disabled regardless of a successful backup.
