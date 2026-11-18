# Runbook: AMP Deno deployment (instance Aedile01)

**Status:** Live since 2026-11-18. **Use for:** updating, restarting, rolling back or checking the production bot.

## What runs where

- Host: luxvps (AMP 2.8.0.10), instance **Aedile01**, module Generic using the **Deno App Runner** template (`CubeCoders/AMPTemplates` `deno-app-runner`), image `cubecoders/ampbase:debian`. UI at 127.0.0.1:8082 behind https://amp.romboter.com.
- Instance settings live in `App.AppSettings` of `/home/amp/.ampdata/instances/Aedile01/GenericModule.kvp`: git repo `https://github.com/Romboter/aedilebot.git`, branch `rewrite/node-ts`, setup commands `deno install; deno task build`, location `bot-ts`, app `dist/main.js`, Deno args `--allow-net --allow-read --allow-write --allow-env`.
- App files: `.../Aedile01/deno-server/app/` (a git clone). Config: `.../deno-server/app/bot-ts/.env` (mode 600, gitignored, never in this repo).
- The previous Python bot is AMP instance **Abot01** on the same host; it is stopped. One token allows one live client: never run both.

## Environment (names only)

`DEPLOYMENT_TOKEN` (same bot token Abot01 used), `NODE_ENV=production`, `ADMIN_USER_IDS`, `ADMIN_GUILD_ID`, optional `STATS_DIR`. `TEST_GUILD_ID` must stay **unset** in production: commands would sync to one guild only (startup logs a warning). `DEV_SERVER_TOKEN` is kept for a dev instance and is ignored in production.

## Update to the latest commit

Preferred: in the instance UI click **Update**, then **Start**. Equivalent from the host, as the `amp` user (running git as root fails with "dubious ownership"):

1. `su - amp -c "ampinstmgr -q Aedile01"`
2. `cd .../deno-server/app && git pull`
3. `cd bot-ts && PATH=.../deno-server/deno:$PATH deno install && deno task build`
4. `su - amp -c "ampinstmgr -s Aedile01"`
5. Check the instance log for `is now running` and `Synced 10 commands:` (no `to guild`).

Pushing to `rewrite/node-ts` does not deploy by itself.

## Roll back

- Code: in the app folder `git checkout <earlier sha>`, rebuild as above, restart.
- Config: previous `.env` copies are beside it (`.env.bak-pre-deploytoken`, `.env.bak-pre-production`).
- Back to the Python bot: stop Aedile01 (`ampinstmgr -q Aedile01`), start Abot01 (`ampinstmgr -s Abot01`). Python re-registers its own commands at startup.

## Known gaps

- No health endpoint or watchdog: a bot whose process is alive but whose gateway is stuck is not detected. Crash restart relies on AMP's auto-retry. See [service operations](service-operations.md) and issue #26.
- Abot01 still has start-on-boot enabled; a host reboot would start the Python bot next to Aedile01 on the same token. Disable it in the Abot01 settings.
- Global commands can lag in clients; refresh the Discord client (Ctrl+R) before assuming a sync failed.
- `/admin_status` reads `bot-ts/stats/`; that folder holds a hash salt, keep it private. Back it up if the counts matter.
