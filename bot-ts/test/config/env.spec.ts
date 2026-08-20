import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { envWarnings, loadEnv } from "../../src/config/env.js";

// loadEnvFile is stubbed so a real bot-ts/.env can't leak into the tests.
describe("config/env", () => {
  beforeEach(() => {
    vi.spyOn(process, "loadEnvFile").mockImplementation(() => undefined);
    vi.stubEnv("DEPLOYMENT_TOKEN", "deploy-token");
    vi.stubEnv("DEV_SERVER_TOKEN", "dev-token");
    vi.stubEnv("https_proxy", undefined);
    vi.stubEnv("TEST_GUILD_ID", undefined);
    vi.stubEnv("MESSAGE_CONTENT", undefined);
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("uses DEV_SERVER_TOKEN outside production, even when DEPLOYMENT_TOKEN is set", () => {
    vi.stubEnv("NODE_ENV", "development");
    expect(loadEnv()).toMatchObject({ token: "dev-token", production: false });
  });

  it("uses DEPLOYMENT_TOKEN in production, even when DEV_SERVER_TOKEN is set", () => {
    vi.stubEnv("NODE_ENV", "production");
    expect(loadEnv()).toMatchObject({ token: "deploy-token", production: true });
  });

  it("throws naming the missing token; never falls back to the other one", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("DEPLOYMENT_TOKEN", undefined);
    expect(() => loadEnv()).toThrow("DEPLOYMENT_TOKEN is not set");
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("DEV_SERVER_TOKEN", undefined);
    expect(() => loadEnv()).toThrow("DEV_SERVER_TOKEN is not set");
  });

  it("messageContent is off unless MESSAGE_CONTENT=true", () => {
    vi.stubEnv("NODE_ENV", "development");
    expect(loadEnv().messageContent).toBe(false);
    vi.stubEnv("MESSAGE_CONTENT", "true");
    expect(loadEnv().messageContent).toBe(true);
  });

  it("reads TEST_GUILD_ID and https_proxy", () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("TEST_GUILD_ID", "123");
    vi.stubEnv("https_proxy", "http://proxy.example");
    expect(loadEnv()).toMatchObject({ testGuildId: "123", httpsProxy: "http://proxy.example" });
  });

  it("swallows a missing .env file", () => {
    vi.spyOn(process, "loadEnvFile").mockImplementation(() => {
      throw new Error("ENOENT");
    });
    vi.stubEnv("NODE_ENV", "development");
    expect(() => loadEnv()).not.toThrow();
  });
});

describe("config/env envWarnings", () => {
  const cfg = (over: object) => ({ token: "t", production: false, httpsProxy: undefined, testGuildId: undefined, messageContent: false, ...over });

  it("warns when production still has TEST_GUILD_ID, because commands would sync to one guild only", () => {
    const w = envWarnings(cfg({ production: true, testGuildId: "1002992031506898954" }));
    expect(w).toHaveLength(1);
    expect(w[0]).toContain("TEST_GUILD_ID");
    expect(w[0]).toContain("1002992031506898954");
  });
  it("is silent for production without a test guild, and for dev with one", () => {
    expect(envWarnings(cfg({ production: true }))).toEqual([]);
    expect(envWarnings(cfg({ production: false, testGuildId: "1" }))).toEqual([]);
  });
});
