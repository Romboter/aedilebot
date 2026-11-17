import { describe, expect, it } from "vitest";
import { defaultDataDir, loadDataSnapshot } from "../../src/data/loader.js";
import { buildCalculatorContext, generalDehuskHandler, generalDisableHandler, generalKillHandler, statsheetHandler } from "../../src/domain/calculator/handlers.js";
import { EntityNotFoundError } from "../../src/domain/errors.js";
import { parseFreeTextQuery } from "../../src/domain/textParsing/freeTextQuery.js";
import { loadFixtures } from "../fixtures.js";

// Python-vs-TypeScript regression matrix (issue #23). Fixture comes from the
// live Python calculator: scripts/generate_regression_matrix.py.
interface Case {
  operation: "kill" | "disable" | "dehusk" | "statsheet";
  input: string[];
  output?: unknown;
  error?: string;
  message?: string;
}
interface FreeText {
  message: string;
  parsed: { weapon: string; target: string; operation: string } | null;
  result?: Case;
}
const { cases, freetext } = loadFixtures<{ cases: Case[]; freetext: FreeText[] }>("regression-matrix.json");
const ctx = buildCalculatorContext(loadDataSnapshot(defaultDataDir()));

function run(c: Case): { output?: unknown; error?: string; message?: string } {
  try {
    const [a, b] = c.input as [string, string];
    if (c.operation === "statsheet") {
      const r = statsheetHandler(ctx, a);
      return r instanceof EntityNotFoundError ? { error: r.constructor.name, message: r.message } : { output: r };
    }
    const fn = { kill: generalKillHandler, disable: generalDisableHandler, dehusk: generalDehuskHandler }[c.operation];
    return { output: fn(ctx, a, b) };
  } catch (e) {
    return { error: (e as Error).constructor.name, message: (e as Error).message };
  }
}

/** Compare one case; returns a description of the mismatch, or undefined. */
function diff(c: Case): string | undefined {
  const got = run(c);
  const want = { output: c.output, error: c.error, message: c.message };
  // Python and JS name error classes alike (EntityNotFoundError, ...) except
  // ZeroDivisionError, which TS surfaces as its own domain error; compare
  // messages, which are what users see, and only require an error on both sides.
  if ((got.error === undefined) !== (want.error === undefined)) {
    return `${c.operation} ${JSON.stringify(c.input)}: want ${JSON.stringify(want)} got ${JSON.stringify(got)}`;
  }
  if (got.error !== undefined) {
    return got.message === want.message ? undefined : `${c.operation} ${JSON.stringify(c.input)}: message want ${want.message} got ${got.message} (${want.error} vs ${got.error})`;
  }
  return JSON.stringify(got.output) === JSON.stringify(want.output) ? undefined : `${c.operation} ${JSON.stringify(c.input)}: want ${JSON.stringify(want.output)} got ${JSON.stringify(got.output)}`;
}

describe("python vs typescript regression matrix", () => {
  for (const op of ["kill", "disable", "dehusk", "statsheet"] as const) {
    it(`${op}: every case matches`, { timeout: 600_000 }, () => {
      const bad = cases.filter((c) => c.operation === op).map(diff).filter((d) => d !== undefined);
      expect(bad.slice(0, 15), `${bad.length} mismatches`).toEqual([]);
    });
  }

  it("free-text queries parse and answer identically", () => {
    const bad: string[] = [];
    for (const f of freetext) {
      const parsed = parseFreeTextQuery(f.message);
      if (JSON.stringify(parsed) !== JSON.stringify(f.parsed)) {
        bad.push(`${f.message}: parsed want ${JSON.stringify(f.parsed)} got ${JSON.stringify(parsed)}`);
        continue;
      }
      if (f.result) {
        const d = diff(f.result);
        if (d) bad.push(`${f.message}: ${d}`);
      }
    }
    expect(bad).toEqual([]);
  });
});
