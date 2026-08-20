// Port of bot.py's run_discord_bot entry point.
//
// Preserved as-is (not fixed here, per the plan): bot.py reads both
// DEPLOYMENT_TOKEN and DEV_SERVER_TOKEN from the environment but only ever
// calls client.run(DEV_SERVER_TOKEN) — a pre-existing inconsistency the plan
// calls out to resolve deliberately at cutover, not as an incidental rewrite
// decision. deploymentToken is loaded (matching Python's own dead read) but
// unused below.
import { loadEnv } from "./config/env.js";
import { buildCalculatorContext } from "./domain/calculator/handlers.js";
import { defaultDataDir, loadDataSnapshot } from "./data/loader.js";
import { createClient, wireClient } from "./gateway/client.js";

const env = loadEnv();
if (env.devServerToken === undefined) {
  throw new Error("DEV_SERVER_TOKEN is not set");
}

const ctx = buildCalculatorContext(loadDataSnapshot(defaultDataDir()));
const client = createClient();
wireClient(client, ctx);

await client.login(env.devServerToken);
