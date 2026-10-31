# Runbook: Configure and test a Discord development bot

**Status:** Implemented for a development bot; zero gateway intents are intentional. **Use for:** validating command behavior and Discord command registration before any release.

## Prerequisites

- Dedicated development Discord application and bot token, not the production bot token.
- Test guild owned/authorized by the operator and its Discord guild snowflake ID.
- A trusted workspace with Node 22 and the rewrite branch tested via [developer setup](developer-setup.md).
- Never paste a bot token in chat, terminal history, screenshots, issues or CI output.

## Procedure

1. In the Discord Developer Portal, select the **development** application. Confirm the token and application identity; use install/invite settings appropriate for application commands.
2. From the bot-ts directory, make a private .env based on the tracked template:
   ~~~bash
   cd bot-ts
   cp .env.example .env
   chmod 600 .env
   ~~~
   Edit .env with DEV_SERVER_TOKEN and TEST_GUILD_ID. The admin allowlist is optional and fail-closed. Do not use the production token here.
3. Run the compiled bot for reproducible testing:
   ~~~bash
   npm ci
   npm run typecheck && npm test && npm run build
   npm start
   ~~~
4. Confirm stdout says the expected test bot user is running and reports command synchronization to the **test guild**, not global. No command sync means there may be an application/login/permission error.
5. In the test guild exercise /help, /kill, /disable, /dehusk, /custom_kill, /bunker_kill, /statsheet and /how. Check known good and invalid inputs and autocomplete.
6. When finished, stop the process cleanly. Confirm there is only one development process using this token.

## Critical behavior

The current Node client requests intents: []. Slash commands function, but ordinary free-text messageCreate parsing does **not** work. Do not “fix” this by silently toggling privileged Message Content; choose an explicit UX and permissions policy under issue #23. TEST_GUILD_ID scopes command registration; without it the code performs global registration, which is **not** suitable for experimenting with the production app.

The /admin_swap command is denied unless ADMIN_USER_IDS and ADMIN_GUILD_ID are both configured. Even when configured, Discord integration permissions may need explicit enabling; real click-through is outstanding issue #12.

## Verify and rollback

**Success:** expected dev application, correct guild, commands work; no unexpected global registration or token use. **Stop:** wrong bot identity, unknown guild, slash sync outside test guild, or log exposes credentials. Stop process; rotate compromised token in Developer Portal; correct .env and restart. No production deployment is involved.

**Sources:** [main.ts](../../bot-ts/src/main.ts), [client.ts](../../bot-ts/src/gateway/client.ts), [command sync](../../bot-ts/src/gateway/commandSync.ts), [env template](../../bot-ts/.env.example).
