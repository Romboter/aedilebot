// Port of bot.py's run_discord_bot: builds the discord.js Client, wires
// on_ready (sync commands), interactionCreate (slash commands +
// autocomplete), and messageCreate (free-text parsing).
//
// Intents: bot.py used `discord.Intents.default()` (every non-privileged
// intent) plus the one privileged intent this bot actually needs
// (message_content, to read on_message text). Rather than blindly
// replicating "every non-privileged intent" — most of which this bot
// doesn't use (presences, bans, invites, etc.) — only the intents the code
// actually subscribes to are requested: Guilds (required for any
// interaction/slash-command traffic) and GuildMessages + MessageContent (for
// on_message free-text parsing). Keeping the privileged-intent surface
// minimal matches the existing memory note that MessageContent is the only
// privileged intent meant to be in use.
import { Client, Events, GatewayIntentBits } from "discord.js";
import type { CalculatorContext } from "../domain/calculator/handlers.js";
import { commands } from "../commands/index.js";
import { createCommandRouter } from "./commandRouter.js";
import { syncCommands } from "./commandSync.js";
import { createMessageListener } from "./messageListener.js";

export function createClient(): Client {
  return new Client({
    intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent],
  });
}

export function wireClient(client: Client, ctx: CalculatorContext): void {
  const routeInteraction = createCommandRouter(commands);

  client.once(Events.ClientReady, (readyClient) => {
    console.log(`${readyClient.user.tag} is now running`);
    syncCommands(readyClient, commands).catch((error: unknown) => {
      console.error(`Sync error: ${String(error)}`);
    });
    console.log("Current discords:");
    for (const guild of readyClient.guilds.cache.values()) {
      console.log(`${guild.name} `);
    }

    const handleMessage = createMessageListener(ctx, readyClient.user.id);
    client.on(Events.MessageCreate, (message) => {
      handleMessage(message).catch((error: unknown) => {
        console.error(error);
      });
    });
  });

  client.on(Events.InteractionCreate, (interaction) => {
    routeInteraction(interaction, ctx).catch((error: unknown) => {
      console.error(error);
    });
  });
}
