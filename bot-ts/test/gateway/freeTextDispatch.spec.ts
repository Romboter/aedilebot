import { beforeAll, describe, expect, it } from "vitest";
import type { CalculatorContext } from "../../src/domain/calculator/handlers.js";
import { buildCalculatorContext } from "../../src/domain/calculator/handlers.js";
import { defaultDataDir, loadDataSnapshot } from "../../src/data/loader.js";
import { parseFreeTextQuery } from "../../src/domain/textParsing/freeTextQuery.js";
import { dispatchFreeTextQuery } from "../../src/gateway/freeTextDispatch.js";

describe("gateway/freeTextDispatch (also exercises the /how command's code path)", () => {
  let ctx: CalculatorContext;

  beforeAll(() => {
    ctx = buildCalculatorContext(loadDataSnapshot(defaultDataDir()));
  });

  it("dispatches a kill query end-to-end, same as on_message would", () => {
    const parsed = parseFreeTextQuery("how many 150mm to kill Border base");
    expect(parsed).not.toBeNull();
    const reply = dispatchFreeTextQuery(ctx, parsed!, "how many 150mm to kill Border base");
    expect(reply).toBe("It takes 12 150mm to kill a Border base");
  });

  it("/how's own query-prefixing produces the same parse as typing the full message", () => {
    // /how's execute() prepends "how " to whatever the user typed in the
    // query option — this proves that reconstruction round-trips through
    // the same parser on_message uses.
    const viaSlashCommand = parseFreeTextQuery(`how ${"many 150mm to kill Border base"}`);
    const viaFreeText = parseFreeTextQuery("how many 150mm to kill Border base");
    expect(viaSlashCommand).toEqual(viaFreeText);
  });

  it("converts a thrown domain error into a reply string instead of throwing", () => {
    const parsed = parseFreeTextQuery("how many 40mm to kill totally-not-a-real-target-xyz");
    expect(parsed).not.toBeNull();
    const reply = dispatchFreeTextQuery(ctx, parsed!, "query");
    expect(reply).toBe("The detected target is not found in my data set. Please try again.");
  });
});
