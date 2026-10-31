# Runbook: CI failures and Python golden fixtures

**Status:** Permanent TypeScript CI is implemented; required status-check enforcement must be verified in GitHub settings (#31). **Use for:** failed PR, fixture drift, TypeScript release checks.

## Understand the jobs

The committed .github/workflows/typescript-ci.yml runs on pushes and PRs targeting rewrite/node-ts:

- Node 22: npm ci, typecheck, Vitest, build, and compiled calculator/fuzzy PluginHost swap/rollback smoke tests.
- Python 3.12: install exact pinned reference packages, generate Python fixtures, fail if tracked test/fixtures differs.

The root release.yaml and unstable.yaml still build the **Python Dockerfile**, not a Node release image.

## Triage procedure

1. Open the PR and GitHub Actions run for its **current head SHA**, not an older green run. Record workflow name, SHA and failed job.
2. If Node job fails: reproduce from a clean checkout by running:
   ~~~bash
   cd bot-ts
   npm ci
   npm run typecheck
   npm test
   npm run build
   ~~~
   Compare failing test and expected behavior against Python fixture, not guesses.
3. If Python job fails: work from the repository root in Python 3.12 with the **exact dependencies pinned in typescript-ci.yml**, then:
   ~~~bash
   python scripts/generate_fixtures.py
   git diff -- test/fixtures/
   ~~~
   Review intended new game data and algorithm changes. Do not hide drift by updating snapshots without understanding why they changed.
4. If compiled-plugin smoke fails: review PluginHost, dist contents, data directory resolution and Node version. Run under compiled Node 22; tsx dev runtime is not the isolation contract.
5. Rerun after fixing; require **both** check jobs to succeed against the latest head.

## Verify success

Both the Node 22 and Python fixture jobs show a **successful conclusion** for the **current PR head SHA**. The source build, fixture diff and compiled plugin smoke test must all be green. If a new commit is pushed while the previous checks are still running, re-check the latest commit rather than accepting stale results.

## Enforce checks

GitHub repository administrator: Settings > Rules > Rulesets (or branch protection) > target rewrite/node-ts > require status checks matching the Node 22 job and Python fixture job. This UI setting is **not** implemented by the workflow file; issue #31 tracks enforcement.

## Failure response

**Stop** merging or deploying when checks are red, cancelled or stale. If baseline data is wrong, fix Python source/fixture generator first and document any deliberate TypeScript divergence. For suspicious CI credentials, abort the run and follow [credentials](credentials.md). Preserve the failed run URL and root cause in the PR.

**Sources:** [CI workflow](../../.github/workflows/typescript-ci.yml), [fixture generator](../../scripts/generate_fixtures.py), [current status](../STATUS.md).
