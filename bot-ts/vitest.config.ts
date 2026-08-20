import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.spec.ts"],
    // Golden fixtures are generated from the Python original by
    // scripts/generate_fixtures.py (repo root) and shared, not duplicated.
    // See test/fixtures.ts for the resolved path.
  },
});
