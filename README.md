# AedileBot

A Discord bot for Foxhole damage calculations: how many hits it takes a weapon to kill, disable or dehusk a target, and what it takes to bring down a bunker.

The bot is written in TypeScript (`bot-ts/`) and runs on Node 22 or later. It replaces the original Python bot, which is no longer the runtime. Its code stays in `src/` as the reference that the golden test fixtures are generated from, and Python scripts in `scripts/` and `tools/` handle game data extraction and audits. Neither is needed to run the bot.

**Where to look next**

| You want to | Go to |
|---|---|
| Run or operate the bot | [Operator handbook](docs/README.md) |
| Know what is live and what is unfinished | [Implementation status](docs/STATUS.md) |
| Understand how it fits together | [Architecture](docs/architecture.md) |
| Set up a development checkout | [Developer setup](docs/runbooks/developer-setup.md) |
| Change game data | [Game data change](docs/runbooks/data-change.md) |

## Commands

Every lookup command has autocomplete. Names are matched fuzzily, so slang and typos mostly work.

| Command | What it does |
|---|---|
| `/kill target weapon` | Hits needed to kill a target |
| `/disable target weapon` | Hits needed to disable a vehicle |
| `/dehusk target weapon` | Hits needed to dehusk a structure |
| `/custom_kill target weapon1 num1 weapon2` | Kill using `num1` hits of `weapon1`, then `weapon2` for the rest |
| `/bunker_kill weapon total_size tier ...` | Bunker kill with garrisons, upgrades and wetness (see below) |
| `/statsheet entity` | Statistics for any weapon, vehicle or structure |
| `/how query` | Free-text form, for example `many mammons to kill a ghouse` |
| `/help` | Command list and data version |
| `/admin_swap`, `/admin_status` | Operator-only; see [Operator commands](#operator-commands) |

`/bunker_kill` takes `weapon`, `total_size` and `tier` (1, 2 or 3). Everything else is optional: `green_dots` and `red_dots` (estimated if you leave them out), garrison counts (`rg`, `mg`, `atg`, `howi`), `shelter`, `obs`, `core`, `ic`, `sc`, `ws`, `fortress`, `radar`, and `wet` (hours since the T3 upgrade, default 24).

```text
/kill target:Silverhand weapon:75mm
/bunker_kill weapon:satchel total_size:15 tier:Tier 3 mg:2 atg:1 howi:1
```

### Free-text questions

With `MESSAGE_CONTENT=true` the bot also answers plain chat such as:

```text
How many 40mm to kill trench?
How many satchels to kill t3 bunker core husk?
How many 68mm to disable HTD?
```

This needs the privileged Message Content intent. Discord has not granted it to the public bot, so there `/how` is the supported route. Self-hosters can switch it on for their own application.

## Running it

Requires Node 22 or later and a Discord bot token from the [Developer Portal](https://discord.com/developers/applications).

```bash
cd bot-ts
cp .env.example .env     # add DEV_SERVER_TOKEN
npm ci
npm run dev              # run from source
```

For a built copy, run `npm run build` and then `npm start`.

### Configuration

The bot reads `bot-ts/.env` if it exists, and plain environment variables either way.

| Variable | Purpose |
|---|---|
| `DEV_SERVER_TOKEN` | Bot token used unless `NODE_ENV=production`. Required in that case. |
| `DEPLOYMENT_TOKEN` | Bot token used when `NODE_ENV=production`. Required in that case. |
| `TEST_GUILD_ID` | Sync slash commands to this one server so they appear immediately. Leave unset in production; the bot warns if both are set. |
| `MESSAGE_CONTENT` | `true` enables free-text chat parsing. Needs the Message Content intent turned on in the Developer Portal. Default off. |
| `ADMIN_USER_IDS` | Comma-separated Discord user IDs of bot operators. |
| `ADMIN_GUILD_ID` | The one server where operator commands are allowed. |
| `STATS_DIR` | Where command-run records are written. Default `bot-ts/stats`. |
| `https_proxy` | HTTP proxy, if you need one. |

The token is chosen by `NODE_ENV` and never falls back to the other one, so a development checkout cannot log in as the production bot.

When you create the Discord application, invite it with the `bot` and `applications.commands` scopes and the Send Messages and Embed Links permissions.

### Docker

```bash
export DEPLOYMENT_TOKEN=your_token
docker compose -f compose.node.yml up -d --build
```

`compose.node.yml` builds from `Dockerfile.node`, restarts on failure, caps logs, and mounts `./data` read-only so game data can be updated without a rebuild. Run only one bot per token. The root `compose.yml` is the old Python bot.

### Operator commands

`/admin_swap` reloads the calculator, fuzzy matcher or data in memory, or rolls the change back. `/admin_status` shows usage, failed lookups and errors from the recorded command runs. Both are disabled unless `ADMIN_USER_IDS` and `ADMIN_GUILD_ID` are set. See [Hot swap](docs/runbooks/hot-swap.md).

### Production

The live bot runs on an AMP host. See the [AMP Deno deployment runbook](docs/runbooks/amp-deno-deployment.md), [Release and cutover](docs/runbooks/release-cutover.md) and [Service operations](docs/runbooks/service-operations.md).

## Game data

Game data lives in [`data/`](data/). It is updated from patch notes or from an exported game build, always as a reviewed change. [Game data change](docs/runbooks/data-change.md) covers the manual path. The extraction and audit tooling lives in `tools/` and `scripts/`; the [handbook](docs/README.md) lists the runbooks for it.

## Troubleshooting

**The bot exits with "DEV_SERVER_TOKEN is not set" or "DEPLOYMENT_TOKEN is not set".** The token that is required depends on `NODE_ENV`. Set the matching variable.

**Slash commands do not appear.** Global commands can take up to an hour to propagate. For immediate testing set `TEST_GUILD_ID` to your server's ID. If it is set in production, commands sync to that server only.

**Free-text questions get no reply.** Set `MESSAGE_CONTENT=true` and enable the Message Content intent for your application in the Developer Portal.

**A name returns nothing.** Check it with `/statsheet`. Lookups that match nothing are listed under `/admin_status`.

More cases are in the [incident response](docs/runbooks/incident-response.md) runbook.

## Contributing

Work happens in `bot-ts/`.

```bash
cd bot-ts
npm test                 # unit and golden-fixture tests
npm run test:regression  # replay the Python-vs-TypeScript regression matrix
npm run typecheck
```

- **Golden fixtures** in `test/fixtures/` come from the Python bot and keep the two implementations in agreement. If a test fails, see [CI and golden fixtures](docs/runbooks/ci-fixtures.md) before editing a fixture.
- **New commands** go in `bot-ts/src/commands/`, with the calculation in `bot-ts/src/domain/`.
- **Pull requests** target `rewrite/node-ts`. Describe the change and how you tested it, and reference any issue.
- Use GitHub Issues for bugs and requests, with steps to reproduce.

```text
aedilebot/
├── bot-ts/        TypeScript bot (src/, test/, docs/)
├── data/          Game data
├── docs/          Handbook, runbooks, status
├── scripts/       Data generation and fixture scripts (Python)
├── tools/         CUE4Parse extractor and game data audit
├── test/          Golden fixtures and Python tests
├── src/           Original Python bot (test oracle, not run)
└── Dockerfile.node, compose.node.yml
```

## License

AGPL-3.0. Network use counts as distribution, so anyone who runs a modified copy for others must offer them the source. Full terms are in [`LICENSE`](LICENSE).

This is a modified version of the original [AedileBot](https://github.com/olted/aedilebot) by olted: the TypeScript rewrite in `bot-ts/` was written in 2026 (see the git history for dates and changes), as AGPL section 5(a) requires us to state.

Main runtime dependencies: `discord.js` (Apache-2.0), `fuzzball` (MIT) and `pluralize` (MIT).
