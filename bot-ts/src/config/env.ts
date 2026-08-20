// Port of bot.py's dotenv-based config (DEPLOYMENT_TOKEN, DEV_SERVER_TOKEN,
// https_proxy env vars). Uses Node's native process.loadEnvFile() (20.6+)
// instead of adding a dotenv dependency — same .env-file behavior, no new
// package. Preserves bot.py's own pre-existing inconsistency deliberately:
// it reads both DEPLOYMENT_TOKEN and DEV_SERVER_TOKEN but only ever calls
// client.run(DEV_SERVER_TOKEN) — see gateway/client.ts. Not fixed here; the
// plan calls this out as something to resolve deliberately at cutover, not
// as an incidental rewrite decision.
export interface EnvConfig {
  deploymentToken: string | undefined;
  devServerToken: string | undefined;
  httpsProxy: string | undefined;
  /** Not in the Python original. When set, slash commands sync to this one
   * guild instead of globally — near-instant propagation for dev-server
   * testing, vs. global registration's up-to-an-hour delay. Leave unset in
   * production. */
  testGuildId: string | undefined;
}

export function loadEnv(): EnvConfig {
  try {
    process.loadEnvFile();
  } catch {
    // No .env file present — fine when real env vars are injected directly
    // (e.g. in production/CI), matching python-dotenv's own no-op-if-missing
    // behavior.
  }
  return {
    deploymentToken: process.env.DEPLOYMENT_TOKEN,
    devServerToken: process.env.DEV_SERVER_TOKEN,
    httpsProxy: process.env.https_proxy,
    testGuildId: process.env.TEST_GUILD_ID,
  };
}
