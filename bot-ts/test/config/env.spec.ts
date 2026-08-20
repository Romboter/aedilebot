import { afterEach, describe, expect, it, vi } from "vitest";
import { loadEnv } from "../../src/config/env.js";

describe("config/env", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("reads DEPLOYMENT_TOKEN, DEV_SERVER_TOKEN, and https_proxy from process.env", () => {
    vi.stubEnv("DEPLOYMENT_TOKEN", "deploy-token");
    vi.stubEnv("DEV_SERVER_TOKEN", "dev-token");
    vi.stubEnv("https_proxy", "http://proxy.example");

    expect(loadEnv()).toEqual({
      deploymentToken: "deploy-token",
      devServerToken: "dev-token",
      httpsProxy: "http://proxy.example",
    });
  });

  it("returns undefined for unset vars rather than throwing", () => {
    vi.stubEnv("DEPLOYMENT_TOKEN", undefined);
    vi.stubEnv("DEV_SERVER_TOKEN", undefined);
    vi.stubEnv("https_proxy", undefined);

    expect(loadEnv()).toEqual({
      deploymentToken: undefined,
      devServerToken: undefined,
      httpsProxy: undefined,
    });
  });
});
