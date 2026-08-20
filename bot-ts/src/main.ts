// Port of bot.py's run_discord_bot entry point.
//
// Preserved as-is (not fixed here, per the plan): bot.py reads both
// DEPLOYMENT_TOKEN and DEV_SERVER_TOKEN from the environment but only ever
// calls client.run(DEV_SERVER_TOKEN) — a pre-existing inconsistency the plan
// calls out to resolve deliberately at cutover, not as an incidental rewrite
// decision. deploymentToken is loaded (matching Python's own dead read) but
// unused below.
import { loadEnv } from "./config/env.js";
import { createClient, wireClient } from "./gateway/client.js";
import { createLiveHosts } from "./gateway/liveContext.js";

const env = loadEnv();
if (env.devServerToken === undefined) {
  throw new Error("DEV_SERVER_TOKEN is not set");
}

const hosts = createLiveHosts();
const client = createClient();
wireClient(client, hosts, env.testGuildId);

await client.login(env.devServerToken);
