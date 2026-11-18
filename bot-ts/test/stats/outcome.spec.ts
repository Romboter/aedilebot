import { describe, expect, it } from "vitest";
import { markOutcome, runWithOutcome } from "../../src/stats/outcome.js";

describe("runWithOutcome", () => {
  it("returns the marked outcome and error type", async () => {
    const r = await runWithOutcome(async () => {
      markOutcome("not_found", "TargetNotFoundError");
    });
    expect(r).toEqual({ outcome: "not_found", errorType: "TargetNotFoundError" });
  });

  it("returns ok when nothing is marked", async () => {
    expect(await runWithOutcome(async () => {})).toEqual({ outcome: "ok" });
  });

  it("captures a thrown error without rethrowing", async () => {
    const boom = new TypeError("boom");
    const r = await runWithOutcome(async () => {
      throw boom;
    });
    expect(r.outcome).toBe("error");
    expect(r.errorType).toBe("TypeError");
    expect(r.thrown).toBe(boom);
  });

  it("first non-ok mark wins", async () => {
    const r = await runWithOutcome(async () => {
      markOutcome("denied");
      markOutcome("error", "X");
    });
    expect(r.outcome).toBe("denied");
  });

  it("markOutcome outside a run is a no-op", () => {
    expect(() => markOutcome("error")).not.toThrow();
  });

  it("concurrent runs do not share marks", async () => {
    const [a, b] = await Promise.all([
      runWithOutcome(async () => {
        await new Promise((r) => setTimeout(r, 10));
        markOutcome("error", "A");
      }),
      runWithOutcome(async () => {
        await new Promise((r) => setTimeout(r, 1));
      }),
    ]);
    expect(a.outcome).toBe("error");
    expect(b.outcome).toBe("ok");
  });
});
