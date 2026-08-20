import { beforeAll, describe, expect, it } from "vitest";
import type { CalculatorContext } from "../../../src/domain/calculator/handlers.js";
import {
  buildCalculatorContext,
  commandBunkerKillHandler,
  customKillHandler,
  generalBunkerKillHandler,
  generalDehuskHandler,
  generalDisableHandler,
  generalKillHandler,
  statsheetHandler,
} from "../../../src/domain/calculator/handlers.js";
import { EntityNotFoundError } from "../../../src/domain/errors.js";
import { defaultDataDir, loadDataSnapshot } from "../../../src/data/loader.js";
import { loadFixtures } from "../../fixtures.js";
import type { BunkerSpec } from "../../../src/domain/calculator/bunkerMath.js";

interface CalculatorFixture {
  id: string;
  operation: "kill" | "disable" | "dehusk" | "custom_kill" | "bunker_direct" | "bunker_freetext" | "statsheet";
  input: unknown[];
  output?: unknown;
  error?: string;
  message?: string;
}

describe("domain/calculator (golden fixture parity)", () => {
  let ctx: CalculatorContext;

  beforeAll(() => {
    ctx = buildCalculatorContext(loadDataSnapshot(defaultDataDir()));
  });

  const fixtures = loadFixtures<CalculatorFixture[]>("calculator-fixtures.json");

  it.each(fixtures)("$id", (fixture) => {
    if (fixture.error !== undefined) {
      expect(() => run(ctx, fixture)).toThrowError(fixture.message);
      return;
    }
    expect(run(ctx, fixture)).toEqual(fixture.output);
  });
});

function run(ctx: CalculatorContext, fixture: CalculatorFixture): unknown {
  const [a, b, c, d] = fixture.input;
  switch (fixture.operation) {
    case "kill":
      return generalKillHandler(ctx, a as string, b as string);
    case "disable":
      return generalDisableHandler(ctx, a as string, b as string);
    case "dehusk":
      return generalDehuskHandler(ctx, a as string, b as string);
    case "custom_kill":
      return customKillHandler(ctx, a as string, b as number, c as string, d as string);
    case "bunker_direct":
      return commandBunkerKillHandler(ctx, a as string, b as BunkerSpec);
    case "bunker_freetext":
      return generalBunkerKillHandler(ctx, a as string, b as string);
    case "statsheet": {
      const result = statsheetHandler(ctx, a as string);
      if (result instanceof EntityNotFoundError) {
        throw result;
      }
      return result;
    }
    default:
      throw new Error(`unknown operation ${fixture.operation as string}`);
  }
}
