# Runbook: Set up a development checkout

**Status:** Implemented workflow; Node 22 CI verified. **Use for:** new maintainer, fresh workstation, reproduction of failed calculations. **Applies to:** rewrite/node-ts, Ubuntu/macOS/Windows with corresponding shell changes.

## Before you start

Install Git, Node 22 and npm; for reference-fixture regeneration also install Python 3.12. You do not need Discord tokens to run typecheck/build/tests. Never clone with production secrets or commit the .env file.

## Procedure

1. Clone and select the rewrite branch (not Python main):
   ~~~bash
   git clone https://github.com/Romboter/aedilebot.git
   cd aedilebot
   git switch rewrite/node-ts
   git status --short --branch
   git rev-parse HEAD
   ~~~
2. Install Node dependencies using the checked-in lockfile:
   ~~~bash
   cd bot-ts
   npm ci
   npm run typecheck
   npm test
   npm run build
   ~~~
3. Confirm compilation produced bot-ts/dist/main.js. Do **not** run npm start until a safe DEV_SERVER_TOKEN has been supplied; this will connect to Discord and register slash commands.
4. For a fast offline Python-baseline check, from repository root:
   ~~~bash
   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install "discord.py==2.7.1" "fuzzywuzzy==0.18.0" "python-Levenshtein==0.27.5" "inflect==7.6.0" "python-dotenv==1.2.4"
   python scripts/generate_fixtures.py
   git diff --exit-code -- test/fixtures/
   ~~~
   Python CI pins these versions; a changed Python dependency can alter singularization and alias fixtures. Do not commit regenerated fixtures without reviewing the differences.

## Verify

Typecheck and tests exit 0; build creates dist/main.js; fixtures exhibit no drift. Record the tested SHA and Node/Python versions in your PR, not as a stale fixed number in documentation.

## If it fails

- npm ci: confirm Node 22; do not delete package-lock.json or use npm install to bypass a lock mismatch.
- Test mismatch: compare generated fixtures and Python dependency versions before changing expectations.
- Runtime import error: ensure compiled dist is current and process was launched from bot-ts.
- Unclean git tree: preserve local edits; use git diff before resetting anything.

**Rollback:** no production state changes occur in offline setup. Clean local generated dist only after verifying you are in the correct checkout and no process is using dist-hotswap copies.

**Sources:** [package.json](../../bot-ts/package.json), [CI workflow](../../.github/workflows/typescript-ci.yml), [fixture generator](../../scripts/generate_fixtures.py), [CI runbook](ci-fixtures.md).
