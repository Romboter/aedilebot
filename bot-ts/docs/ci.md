# Continuous integration for the TypeScript rewrite

The canonical GitHub Actions workflow is .github/workflows/typescript-ci.yml.

## On every PR to rewrite/node-ts and every push to rewrite/node-ts

- **Node 22:** clean npm ci from the committed lockfile, TypeScript typecheck, the entire Vitest suite, production build and a real compiled calculator/fuzzy hot-swap+rollback smoke test.
- **Python fixture drift:** run the committed fixture generator under Python 3.12 with exact reference dependency versions; fail if any generated test/fixtures snapshot differs. Fixtures must be intentionally refreshed and reviewed, not silently rewritten by the workflow.
- GitHub Actions records the tested commit SHA, output and failures.

Both jobs require no bot token or privileged app credentials, making pull-request execution safe for untrusted changes.

## Before merging into rewrite/node-ts

Confirm both status checks are green on the *current PR head*. The GitHub connector in this environment can create workflows but cannot configure repository branch protection. To enforce this automatically, enable **Require status checks to pass before merging** under repository Rulesets/branch protection for rewrite/node-ts, and select the Node 22 and Python golden-fixture checks.

A passing CI run proves build and test behavior, not a successful live Discord click-through, a production cutover, hot-swapping of external npm dependencies, or operation of AMP containers. Those are separate issues (#12 and #26).

Historical per-issue validation workflows for #22, #10 and #11 were superseded by this permanent workflow and removed from the repository.
