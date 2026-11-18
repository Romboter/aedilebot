// Config from the environment (and bot-ts/.env if present, via Node's native
// process.loadEnvFile(), no dotenv dependency).
//
// Token selection is explicit, never "whichever is set":
//   NODE_ENV=production -> DEPLOYMENT_TOKEN (required)
//   anything else       -> DEV_SERVER_TOKEN (required)
// so a dev checkout with both tokens in .env can never log in as the
// production bot, and the production container (NODE_ENV=production) can
// never silently fall back to a dev token.
export interface EnvConfig {
  /** The token this process logs in with, chosen per NODE_ENV (see above). */
  token: string;
  production: boolean;
  httpsProxy: string | undefined;
  /** When set, slash commands sync to this one guild instead of globally:
   * near-instant propagation for dev testing vs. up to an hour. Leave unset
   * in production. */
  testGuildId: string | undefined;
  /** MESSAGE_CONTENT=true turns on the Guilds/GuildMessages/MessageContent
   * intents so free-text "how many X to kill Y" chat parsing works. Off by
   * default: MessageContent is privileged and Discord has not granted it to
   * the public bot. Self-hosters can enable it (and the Developer Portal
   * toggle) since the restriction does not apply to their own app. */
  messageContent: boolean;
}

export function loadEnv(): EnvConfig {
  try {
    process.loadEnvFile();
  } catch {
    // No .env file: fine when real env vars are injected directly.
  }
  const production = process.env.NODE_ENV === "production";
  const name = production ? "DEPLOYMENT_TOKEN" : "DEV_SERVER_TOKEN";
  const token = process.env[name];
  if (!token) {
    throw new Error(`${name} is not set (required when NODE_ENV${production ? "=" : "!="}production)`);
  }
  return {
    token,
    production,
    httpsProxy: process.env.https_proxy,
    testGuildId: process.env.TEST_GUILD_ID,
    messageContent: process.env.MESSAGE_CONTENT === "true",
  };
}

/** Misconfigurations that are legal but almost certainly unintended. */
export function envWarnings(env: EnvConfig): string[] {
  const warnings: string[] = [];
  if (env.production && env.testGuildId !== undefined && env.testGuildId !== "") {
    warnings.push(
      `NODE_ENV=production but TEST_GUILD_ID=${env.testGuildId} is set: slash commands will sync to that one guild only, not globally. Unset TEST_GUILD_ID for a live bot.`,
    );
  }
  return warnings;
}
