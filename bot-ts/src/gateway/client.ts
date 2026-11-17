// Port of bot.py's run_discord_bot: builds the discord.js Client, wires
// on_ready (sync commands), interactionCreate (slash commands +
// autocomplete), and messageCreate (free-text parsing).
//
// Intents: none by default. Slash commands and autocomplete are delivered
// regardless of intents. messageContent=true (MESSAGE_CONTENT=true in env)
// adds Guilds/GuildMessages/MessageContent so the free-text chat listener
// works; MessageContent is privileged, so the app must also have it enabled
// in the Developer Portal (Discord has not granted it to the public bot).
import { Client, Events, GatewayIntentBits } from "discord.js";
import type { LiveHosts } from "./liveContext.js";
import { commands } from "../commands/index.js";
import { createCommandRouter } from "./commandRouter.js";
import { syncCommands } from "./commandSync.js";
import { createMessageListener } from "./messageListener.js";

export function createClient(messageContent = false): Client {
  const intents = messageContent
    ? [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent]
    : [];
  return new Client({ intents });
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
