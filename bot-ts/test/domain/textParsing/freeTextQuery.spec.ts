import { describe, expect, it } from "vitest";
import { parseFreeTextQuery } from "../../../src/domain/textParsing/freeTextQuery.js";
import { loadFixtures } from "../../fixtures.js";

interface FreeTextFixture {
  message: string;
  result: { weapon: string; target: string; operation: string } | null;
}

describe("domain/textParsing/freeTextQuery (golden fixture parity)", () => {
  const fixtures = loadFixtures<FreeTextFixture[]>("freetext-query-fixtures.json");

  it.each(fixtures)("$message", (fixture) => {
    expect(parseFreeTextQuery(fixture.message)).toEqual(fixture.result);
  });
});
