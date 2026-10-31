# Runbook: Credentials, permissions and rotation

**Status:** Dev token and admin allowlist are implemented; production token selection/secure deployment strategy pending #25. **Use for:** operator onboarding, lost credentials, suspected exposure, Steam runner provisioning.

## Inventory of sensitive items (names only)

- Discord DEV_SERVER_TOKEN; an older DEPLOYMENT_TOKEN exists in Python/Node config but **Node main.ts currently logs in only with DEV_SERVER_TOKEN**.
- ADMIN_USER_IDS and ADMIN_GUILD_ID enable bot-global /admin_swap only if **both** match the caller/guild; no arbitrary module paths allowed.
- TEST_GUILD_ID scopes slash command updates during testing; omit only when deliberately intending global registration.
- Steam login and persistent Steam Guard session on the isolated extraction runner.
- GitHub private automation repository access, runner registration credentials, environment settings and private archive storage.
- User queries may appear in error_log.txt; review log access/retention.

## Secure provisioning

1. Use distinct development and production applications/tokens; store credentials in an OS-protected service environment or secret store, not shell history, public repo files or issue comments.
2. Start with bot-ts/.env.example only for a development workstation; set permissions:
   ~~~bash
   cd bot-ts
   cp .env.example .env
   chmod 600 .env
   ~~~
   Replace placeholders locally; never paste the actual values in tickets.
3. Use real Discord snowflake IDs for the trusted bot operator and guild. Configure Discord Integration command permissions in that trusted guild; all other guilds must remain unauthorized.
4. Use a **private** repository for authenticated extraction workflow. The AedileBot repo is public; do not register a credentialed self-hosted runner against it, and do not mount Docker sockets or unrelated application storage.
5. Grant the runner only read/write access to its private work/archive volume. Perform Steam Guard bootstrap locally under the same non-root identity that runs the jobs.

## Rotation or compromise response

1. **Contain:** disable the affected bot or runner immediately, revoke bot tokens in Discord Developer Portal and invalidate affected sessions/keys. If a credential entered Git history, remove access **first**; deleting the current file alone does not expunge history.
2. Generate a new credential and update only its approved secret-store/service environment. Re-test on staging using a known guild/command. Review logs for unexpected successful admin_swap events.
3. For Steam Guard exposure, terminate logged-in sessions/change password as appropriate, then locally reauthenticate the isolated runner.
4. Record incident timeline, who was authorized, which apps/hosts were touched and how recurrence is prevented. Never include a raw secret in the incident report.

## Validation

Expected application identity in Discord; admin command denied to an outsider; allowed operator works only in trusted guild; zero credential values in logs and Git diffs. If unknown, keep the bot/runner disabled and escalate.

**Sources:** [env template](../../bot-ts/.env.example), [admin authorization](../../bot-ts/src/commands/adminSwap.ts), [issue #25](https://github.com/Romboter/aedilebot/issues/25).
