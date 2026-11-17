import { loadEnv } from "./config/env.js";
import { createClient, wireClient } from "./gateway/client.js";
import { createLiveHosts } from "./gateway/liveContext.js";

const env = loadEnv();
const hosts = createLiveHosts();
const client = createClient(env.messageContent);
wireClient(client, hosts, env.testGuildId);

await client.login(env.token);
