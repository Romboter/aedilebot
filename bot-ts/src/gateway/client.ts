// Port of bot.py's run_discord_bot: builds the discord.js Client, wires
// on_ready (sync commands), interactionCreate (slash commands +
// autocomplete), and messageCreate (free-text parsing).
//
// Intents: deliberately requesting ZERO gateway intents right now (user
// decision, dev-bot testing) — slash-command interactions are delivered
// regardless of intents (they're not gated by GatewayIntentBits at all), so
// /help, /kill, /how, etc. all keep working. The cost: no Guilds intent
// means readyClient.guilds.cache stays empty (the "Current discords:"
// logging below prints nothing), and no GuildMessages/MessageContent means
// messageCreate events never arrive, so createMessageListener's free-text
// "how many X to kill Y" chat parsing is wired below but effectively inert
// until intents are restored. To bring it back: add
// GatewayIntentBits.Guilds, GuildMessages, and MessageContent (the last one
// is privileged — must also be toggled on in the Discord Developer Portal's
// Bot settings for this application before Discord will allow it).
import { Client, Events } from "discord.js";
import type { LiveHosts } from "./liveContext.js";
import { commands } from "../commands/index.js";
import { createCommandRouter } from "./commandRouter.js";
import { syncCommands } from "./commandSync.js";
import { createMessageListener } from "./messageListener.js";

export function createClient(): Client {
  return new Client({ intents: [] });
}

export function wireClient(client: Client, hosts: LiveHosts, testGuildId?: string): void {
  const routeInteraction = createCommandRouter(commands);

  client.once(Events.ClientReady, (readyClient) => {
    console.log(`${readyClient.user.tag} is now running`);
    syncCommands(readyClient, commands, testGuildId).catch((error: unknown) => {
      console.error(`Sync error: ${String(error)}`);
    });
    console.log("Current discords:");
    for (const guild of readyClient.guilds.cache.values()) {
      // Without the Guilds intent, READY only includes unavailable guild
      // stubs (no name) — skip those rather than logging "undefined".
      if (guild.name) {
        console.log(`${guild.name} `);
      }
    }

    const handleMessage = createMessageListener(hosts, readyClient.user.id);
    client.on(Events.MessageCreate, (message) => {
      handleMessage(message).catch((error: unknown) => {
        console.error(error);
      });
    });
  });

  client.on(Events.InteractionCreate, (interaction) => {
    routeInteraction(interaction, hosts).catch((error: unknown) => {
      console.error(error);
    });
  });
}
