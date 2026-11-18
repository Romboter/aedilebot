# `/admin_status` operator command and command-run recording

Status: draft, awaiting approval. Branch: `rewrite/node-ts` (bot-ts).

## Intent

The operator (Jason) wants to check on the bot: how big it is, whether it is healthy, and how it is being used. Today the only visibility is the console log. This adds (1) recording of every slash-command run and (2) a `/admin_status` command that shows the result, visible only to the operator.

## Goals

- One new command, `/admin_status`, replying ephemerally with a single embed.
- Record every slash-command run with: time, command name, guild ID, options picked, outcome (success or failure with error type), response time, and a hashed user ID.
- Show, in the embed, everything the operator asked for:
  - **Bot:** server count, largest servers by member count, uptime and start time, Discord ping, bot version and git commit.
  - **Game data:** weapon, target and vehicle counts, which data version is live, which plugin modules are live, last `/admin_swap` or rollback.
  - **Usage:** total commands, per-command counts, unique users, most-queried weapons and targets.
  - **Problems:** failed lookups and fuzzy-match misses (which names people typed that matched nothing), errors per day.
- Counters survive restarts and redeploys, including the AMP deployment.

## Non-goals

- No public stats; players never see this.
- No dashboard, web page or export.
- No recording of free-text chat messages (`messageListener`); slash commands only, because chat parsing is off by default.
- No raw Discord user IDs, no usernames, no free-text `/how` query text on disk (see privacy).
- No pruning or rotation of the record file for now.

## Anti-goals

- It must never slow down or break a normal command. A failure to write a record is logged and swallowed.
- It must never leak the raw user ID, token or `.env` values anywhere.
- Anyone other than the operator running `/admin_status` gets a refusal, not data.

## Decisions made with the operator

- Audience: the operator only, user ID `237387841678606336`.
- Recorded per run: guild, options picked, success or failure, response time.
- User identity stored as a hash so unique users can be counted.
- All the listed stats are wanted (free ones and counter-based ones).

## Calls made by the designer (the operator has not seen these)

- **Hash:** salted SHA-256 of the user ID. Salt is random, generated on first use, stored next to the record file, never in git.
- **Storage:** an append-only JSON Lines file, one record per run, in a `stats/` directory. Directory is `STATS_DIR` if set, else `stats/` beside `dist/`'s parent (`bot-ts/stats/`). Gitignored. On AMP this sits in the cloned app folder, which `git pull` does not remove.
- **Aggregation:** `/admin_status` reads and aggregates the file on demand. Volume is small, so no database and no in-memory counters to lose.
- **Access check:** `/admin_status` and `/admin_swap` are both operator-only (the operator's words), driven by the same `ADMIN_USER_IDS` variable, which will hold only the operator's ID. `/admin_status` checks the user only, with no `ADMIN_GUILD_ID` requirement, because the reply is ephemeral. `/admin_swap` keeps its existing user-plus-guild rule unchanged. Both `.env` files (local and the AMP instance) need `ADMIN_USER_IDS=237387841678606336`; `/admin_swap` also needs `ADMIN_GUILD_ID` set to the test guild.
- **Where recording happens:** in `gateway/commandRouter.ts`, around `command.execute`, so every command is covered in one place and no command file changes.
- **`/how` query text:** the options recorded for `/how` are the parsed weapon and target and the operation, not the raw string.
- **`/admin_status` is not recorded** in its own usage counts.
- **Registration:** added to `commands/index.ts` like the others; it appears in the guild's slash list but is refused for everyone but the operator. It is left out of `/help`.
- **Outcome values:** `ok`, `not_found` (name matched nothing), `error` (anything thrown or presented as an error).

## Constraints

- TypeScript on Node 22, run on AMP under Deno 2 from compiled `dist/`. Use only `node:` built-ins (`fs`, `crypto`); no new dependencies.
- File writes must work under Deno with `--allow-write` and in the AMP container (writes to the app directory already happen for `error_log.txt`).
- Embed limits: at most 25 fields, 1024 characters per field value; truncate long lists.
- Keep `domain/*` and `data/*` free of discord.js imports, as today.

## Left to the builder

- Exactly how to detect `not_found` versus `error`. Commands currently turn domain errors into reply text themselves (`gateway/errorPresenter.ts`), so the router may need a small signal from them. Pick the smallest change that works, and keep recorded outcomes honest.
- Embed layout and wording.
- Window for "errors per day" (suggest last 7 days) and top-N lists (suggest 5).
- Where the git commit comes from (build-time stamp, or read `.git` if present; show "unknown" if not).
- Tests: record writing, hashing, aggregation, the access check, and that a failing write does not break a command.

## Open questions for the operator

1. Should `/admin_status` be registered only in the test guild (as now) or also globally later? Assumed: follows the existing sync behaviour.
2. Is keeping the record file forever acceptable until it gets large, or should it prune old runs (for example after 90 days)? Assumed: keep forever for now.
