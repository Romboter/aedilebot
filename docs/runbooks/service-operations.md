# Runbook: Day-to-day service checks and safe restart

**Status:** Python Docker/Compose definitions exist; live AMP/container placement and Linux service names are **not verified**. Node supervision/health checks are pending #26. **Use for:** bot appears offline, no slash responses, maintenance restart.

## First identify the actual runtime

1. Check the host and deployment inventory privately (AMP instance, Docker Compose folder, systemd unit or bare process). Never assume an instance name.
2. On Ubuntu, read-only triage:
   ~~~bash
   uptime
   df -h
   free -h
   sudo systemctl --failed
   docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
   ~~~
   Use docker only where installed and authorized. Distinguish game server failures from bot failures.
3. Confirm which application/bot account is expected in Discord, and whether a single instance owns its token.

## Docker/Compose Python deployment (only if this is the deployed method)

From the directory containing the *actual* compose.yml, inspect:
~~~bash
docker compose config --services
docker compose ps
docker compose logs --tail=150 aedile
~~~
The checked-in service name is aedile; this example is valid only when that Compose file is deployed. Do not print docker compose config without reviewing secret exposure; environment may contain tokens.

To safely restart **after verifying this is the active service and approved**:
~~~bash
docker compose restart aedile
docker compose ps
docker compose logs --tail=80 aedile
~~~
Note: compose.yml passes DEV_SERVER_TOKEN and root Dockerfile runs Python. This is not a vetted production Node deployment recipe.

## Node development process

When running the compiled development bot, check its process/logs through the supervisor actually used. No systemd unit name, Docker image or HTTP readiness endpoint has been standardized. To reproduce locally (development token only):
~~~bash
cd bot-ts
npm run typecheck && npm test && npm run build
npm start
~~~
Admin plugin swaps avoid downtime for supported code/data changes; they are **not** crash recovery. A process supervisor must handle crashes (#26).

## Verify and escalation

Check expected bot identity, successful login, command sync to intended guild and a known /kill and /help response. If commands fail after a code release, follow [release rollback](release-cutover.md); if data is wrong follow [data change](data-change.md). Preserve service logs with sensitive queries/tokens redacted.

**Stop** if two production clients are active, token identity mismatches, disk is full, or the service restart would affect other AMP games. Do not use system-wide reboots to diagnose a single bot. Escalate to host owner if the runtime cannot be confidently identified.
