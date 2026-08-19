import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

// Golden fixtures live at repo root (test/fixtures/*.json), generated from
// the live Python calculator by scripts/generate_fixtures.py, not duplicated
// under bot-ts/ so there is exactly one source of truth to regenerate.
const repoRoot = path.resolve(fileURLToPath(import.meta.url), "../../..");
const fixturesDir = path.join(repoRoot, "test", "fixtures");

export function loadFixtures<T>(filename: string): T {
  const raw = readFileSync(path.join(fixturesDir, filename), "utf-8");
  return JSON.parse(raw) as T;
}
