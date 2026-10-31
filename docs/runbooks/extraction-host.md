# Runbook: Provision an isolated Ubuntu map-extraction host

**Status: PROPOSED / NOT PROVISIONED.** The Linux exporter has compiled/started on a hosted runner, but no licensed Steam download on an AMP Ubuntu machine has been verified. Real scripts currently reside in **unmerged draft PR #39**, not rewrite/node-ts. **Use for:** building a new extraction worker or replacing one.

## Isolation decision

Romboter/aedilebot is PUBLIC. Do not register an authenticated persistent self-hosted GitHub runner against this repository. Use a dedicated Ubuntu 24.04 VM or strongly isolated container on an AMP host, with the **actual workflow in a private automation repository**. A VM with no host Docker socket, AMP credentials or mounted game-server files is preferable.

### Capacity / account prerequisites

- Dedicated non-root service identity and persistent workspace with at least 80 GiB **initial** allocation; use separate filesystem where possible and monitor archive growth. This is a planning estimate, not guaranteed future capacity.
- Access to a Steam account entitled to download Foxhole, capable of local Steam Guard verification.
- Internet/DNS, Git, Python 3.12 environment, .NET 10 SDK, SteamCMD i386, zstd CLI for restore and GitHub Actions runner if using a private dispatch repo.
- Isolation policy: only authorized trusted maintainers can change this worker's scripts or read its Steam state.

## Provisioning steps (in an isolated Ubuntu instance)

1. Inventory disk/memory and mounted volumes **before** installation:
   ~~~bash
   df -h
   lsblk -f
   free -h
   id
   ~~~
2. Install SteamCMD prerequisites. Run sudo only for package/system changes:
   ~~~bash
   sudo dpkg --add-architecture i386
   sudo add-apt-repository -y multiverse
   sudo apt-get update
   sudo apt-get install -y steamcmd:i386 git python3 python3-venv zstd
   ~~~
   Set up the supported .NET 10 SDK using its official Linux instructions or the private workflow's setup-dotnet action; verify dotnet --info. Do not install unreviewed remote shell scripts as root.
3. Create a **private persistent volume**, owned by the dedicated runner account. Example only (replace USER and mount path with your environment):
   ~~~bash
   sudo install -d -m 0700 -o RUNNER_USER -g RUNNER_USER /srv/foxhole-extract
   ~~~
   The above fails if RUNNER_USER does not already exist; intentionally create/manage the identity through your organization standard first.
4. Install/register GitHub's self-hosted runner using documented GitHub instructions, **only for the private automation repo**, under that non-root identity. Label it foxhole-extract and restrict repository write/PR access. Do not start with unrestricted host mounts.
5. Authenticate SteamCMD **interactively as the runner identity**, then verify session persistence by repeating the command in [Steam map export](steam-map-export.md) from a separate login under the same identity.
6. Set private-repo environment variables FOXHOLE_WORK_ROOT, FOXHOLE_STEAMCMD_PATH, FOXHOLE_STEAM_USER and required environment approvals. Copy the reviewed workflow template from draft PR #39 into the private repo; pin an audited commit SHA.
7. Install Python extraction dependencies inside an isolated Python environment, not system Python:
   ~~~bash
   python3 -m venv /srv/foxhole-extract/.venv
   /srv/foxhole-extract/.venv/bin/python -m pip install -r tools/map-extraction/requirements.txt
   ~~~
   The tools path is available only after checking out reviewed PR code. Configure the workflow interpreter/venv consistently.

## Verification and stop conditions

From the actual worker: confirm mount ownership, space, git, dotnet, python3, /usr/games/steamcmd, outbound HTTPS and ability to run **offline** extractor tests. Record install command versions and reviewed SHA. Never run an untrusted PR job against this host.

**Stop** if host-only Docker socket, production game-server data or secrets are visible inside the worker; if Steam account has not authorized the download; or if it lacks sufficient disk. Tear down runner registration before repurposing the VM. Follow [credentials](credentials.md) for revocation.

**References:** [map export runbook](steam-map-export.md), [draft #39](https://github.com/Romboter/aedilebot/pull/39), [Steam pipeline issue #38](https://github.com/Romboter/aedilebot/issues/38).
