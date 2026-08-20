import { describe, expect, it, vi } from "vitest";
import { presentError } from "../../src/gateway/errorPresenter.js";
import {
  BunkerSpecParseError,
  EntityNotFoundError,
  InvalidTypeError,
  NoDamageError,
  TargetNotFoundError,
  TargetOfTypeNotFoundError,
  WeaponNotFoundError,
} from "../../src/domain/errors.js";

describe("gateway/errorPresenter", () => {
  it("NoDamageError: returns its message without logging", () => {
    const logger = vi.fn();
    const result = presentError(new NoDamageError("7.62mm", "Hades Net"), "query text", logger);
    expect(result).toBe("This weapon (7.62mm) does no damage to this entity (Hades Net).");
    expect(logger).not.toHaveBeenCalled();
  });

  it("TargetNotFoundError: returns its message and logs the class name", () => {
    const logger = vi.fn();
    const result = presentError(new TargetNotFoundError("xyz"), "query text", logger);
    expect(result).toBe("The detected target is not found in my data set. Please try again.");
    expect(logger).toHaveBeenCalledWith("TargetNotFoundError", "query text");
  });

  it("BunkerSpecParseError (a TargetNotFoundError subclass): returns its own hint message", () => {
    const logger = vi.fn();
    const result = presentError(new BunkerSpecParseError("size xyz"), undefined, logger);
    expect(result).toContain("Invalid bunker specification");
    expect(logger).toHaveBeenCalledWith("BunkerSpecParseError", undefined);
  });

  it("TargetOfTypeNotFoundError: falls through to the generic EntityNotFoundError branch", () => {
    const logger = vi.fn();
    const result = presentError(new TargetOfTypeNotFoundError("xyz"), "q", logger);
    expect(result).toBe("The detected target for this operation is not found in my data set. Please try again.");
    expect(logger).toHaveBeenCalledWith("TargetOfTypeNotFoundError", "q");
  });

  it("InvalidTypeError: returns its message and logs the class name", () => {
    const logger = vi.fn();
    const result = presentError(new InvalidTypeError("xyz"), "q", logger);
    expect(result).toBe("The entity was invalid for this operation. Please try again.");
    expect(logger).toHaveBeenCalledWith("InvalidTypeError", "q");
  });

  it("WeaponNotFoundError: returns its message and logs the class name", () => {
    const logger = vi.fn();
    const result = presentError(new WeaponNotFoundError("xyz"), "q", logger);
    expect(result).toBe("The detected weapon is not found in my data set. Please try again.");
    expect(logger).toHaveBeenCalledWith("WeaponNotFoundError", "q");
  });

  it("EntityNotFoundError: returns its message and logs the class name", () => {
    const logger = vi.fn();
    const result = presentError(new EntityNotFoundError("xyz"), "q", logger);
    expect(result).toBe("The requested entity was not found. Please try again.");
    expect(logger).toHaveBeenCalledWith("EntityNotFoundError", "q");
  });

  it("unrecognized error: generic message, logged as Exception", () => {
    const logger = vi.fn();
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const result = presentError(new Error("boom"), "q", logger);
    expect(result).toBe("Inner error happened during processing of your request. Please, contact bot's devs about this.");
    expect(logger).toHaveBeenCalledWith("Exception", "q");
    consoleSpy.mockRestore();
  });
});
