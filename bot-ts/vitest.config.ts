import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.spec.ts"],
    // The Python-vs-TS matrix replays ~14k queries (minutes); run it with
    // `npm run test:regression`, not on every `npm test`.
    exclude: process.env.REGRESSION ? [] : ["node_modules/**", "test/regression/**"],
    // Golden fixtures are generated from the Python original by
    // scripts/generate_fixtures.py (repo root) and shared, not duplicated.
    // See test/fixtures.ts for the resolved path.
  },
});
