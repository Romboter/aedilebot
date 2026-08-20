import { afterEach, describe, expect, it, vi } from "vitest";
import { loadEnv } from "../../src/config/env.js";

// process.loadEnvFile() reads the real bot-ts/.env from disk if present -
// stubbed out here so these tests are deterministic regardless of whether a
// real .env exists (it does, for live dev-server testing) or what it
// contains.
describe("config/env", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("reads DEPLOYMENT_TOKEN, DEV_SERVER_TOKEN, https_proxy, and TEST_GUILD_ID from process.env", () => {
    vi.spyOn(process, "loadEnvFile").mockImplementation(() => undefined);
    vi.stubEnv("DEPLOYMENT_TOKEN", "deploy-token");
    vi.stubEnv("DEV_SERVER_TOKEN", "dev-token");
    vi.stubEnv("https_proxy", "http://proxy.example");
    vi.stubEnv("TEST_GUILD_ID", "123456789");

    expect(loadEnv()).toEqual({
      deploymentToken: "deploy-token",
      devServerToken: "dev-token",
      httpsProxy: "http://proxy.example",
      testGuildId: "123456789",
    });
  });

  it("returns undefined for unset vars rather than throwing", () => {
    vi.spyOn(process, "loadEnvFile").mockImplementation(() => undefined);
    vi.stubEnv("DEPLOYMENT_TOKEN", undefined);
    vi.stubEnv("DEV_SERVER_TOKEN", undefined);
    vi.stubEnv("https_proxy", undefined);
    vi.stubEnv("TEST_GUILD_ID", undefined);

    expect(loadEnv()).toEqual({
      deploymentToken: undefined,
      devServerToken: undefined,
      httpsProxy: undefined,
      testGuildId: undefined,
    });
  });

  it("swallows a missing/unreadable .env file instead of throwing", () => {
    vi.spyOn(process, "loadEnvFile").mockImplementation(() => {
      throw new Error("ENOENT: no such file");
    });
    vi.stubEnv("DEV_SERVER_TOKEN", undefined);

    expect(() => loadEnv()).not.toThrow();
    expect(loadEnv().devServerToken).toBeUndefined();
  });
});
