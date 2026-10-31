# Runbook: Host extraction alongside existing AMP servers without affecting games

**Status: DEPLOYMENT DESIGN — not installed on an AMP host.** The operators have Ubuntu hosts running CubeCoders AMP game servers, but the specific current AMP instance names, storage paths and network configuration must be verified locally. **Use for:** allocating a separate extraction VM/workload on an AMP machine.

## Scope and boundaries

Do **not** configure Foxhole extraction as another AMP game server solely to obtain scheduling. This pipeline downloads large game content, compiles .NET, retains historical archives and needs a private GitHub runner. Start with an isolated Ubuntu VM or tightly constrained container under the Ubuntu host's standard virtualization/container management. Avoid guest access to host Docker socket, SSH keys, AMP instance data or other game-server storage.

## Host preflight (read only)

~~~bash
cat /etc/os-release
df -h
lsblk -f
free -h
uptime
sudo systemctl --failed
sudo ss -tulpn
~~~

If AMP instance tooling is available under the amp service user, inspect it without making changes:

~~~bash
sudo -u amp -H ampinstmgr list
~~~

This command assumes the AMP service user is named amp and the command exists; if not, use the host's documented AMP management interface. Avoid running an AMP update during extraction or server peak load.

## Resource allocation

1. Inventory actual free storage and existing AMP/VM reservations. **80 GiB is an initial estimate only**; account for future private archived snapshots, build output, game updates and backups. Never allocate based solely on total volume size.
2. Set explicit CPU/RAM/IO limits for the new workload and schedule downloads/exports outside game peak hours. Watch I/O wait and storage latency under load.
3. Reserve a persistent private storage mount for game install, Steam Guard session and archive. Keep guest runner non-root.
4. Apply firewall/egress rules to allow only required GitHub/Steam/Git/.NET endpoints. This workload does not need inbound game ports.
5. Arrange private off-host backups separately from the AMP game-data backup policy.

## Commission and verify

- Confirm game servers remain accessible and operating normally during a small, offline exporter smoke test.
- Verify the extractor VM has no cross-access to AMP credentials, other game directories, host Docker socket or host network management.
- Run real SteamCMD download only after entitled account bootstrap and a maintenance/resource window. Monitor host CPU/I/O/disk during it.
- Check generated JSON inventory and retained archive on guest private storage; never publish the full assets to public repo.

## Rollback

If guest workload degrades AMP game servers, stop the extraction job and its VM/container; avoid stopping/restarting unrelated AMP instances. Preserve the archive and diagnostic logs for reconfiguration. Reclaim only the dedicated, positively identified guest resources after a backup/ownership check.

**Related:** [host provisioning](extraction-host.md), [private runner](private-actions-runner.md), [service operations](service-operations.md), [incident response](incident-response.md).
