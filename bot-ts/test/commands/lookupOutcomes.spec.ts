import { describe, expect, it, vi } from "vitest";
import type { ChatInputCommandInteraction } from "discord.js";
import type { CalculatorContext } from "../../src/domain/calculator/handlers.js";
import { EntityNotFoundError } from "../../src/domain/errors.js";
import { runWithOutcome } from "../../src/stats/outcome.js";
import { how } from "../../src/commands/how.js";
import { statsheet } from "../../src/commands/statsheet.js";

vi.mock("../../src/domain/calculator/handlers.js", async (orig) => ({
  ...(await orig<typeof import("../../src/domain/calculator/handlers.js")>()),
  statsheetHandler: () => new EntityNotFoundError("asdf"),
}));

const fake = (opt: string) =>
  ({ options: { getString: () => opt }, reply: vi.fn().mockResolvedValue(undefined) }) as unknown as ChatInputCommandInteraction;

describe("lookups that find nothing are recorded as not_found", () => {
  it("/how with unparseable text", async () => {
    const r = await runWithOutcome(() => how.execute(fake("gibberish zzz"), {} as CalculatorContext, {} as never));
    expect(r).toMatchObject({ outcome: "not_found", errorType: "NoMatch" });
  });

  it("/statsheet with an unknown entity", async () => {
    const r = await runWithOutcome(() => statsheet.execute(fake("asdf"), {} as CalculatorContext, {} as never));
    expect(r.outcome).toBe("not_found");
    expect(r.errorType).toBe("EntityNotFoundError");
  });
});
