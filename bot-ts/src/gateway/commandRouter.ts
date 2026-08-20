// Dispatches discord.js Interaction events to the matching SlashCommand's
// execute/autocomplete handler by command name (and, for autocomplete, by
// which option is focused) — the plain-function equivalent of bot.py's
// @client.tree.command/@x.autocomplete decorator stack.
import type { Interaction } from "discord.js";
import type { CalculatorContext } from "../domain/calculator/handlers.js";
import type { SlashCommand } from "./command.js";

export function createCommandRouter(commands: SlashCommand[]) {
  const byName = new Map(commands.map((command) => [command.data.name, command]));

  return async function handleInteraction(interaction: Interaction, ctx: CalculatorContext): Promise<void> {
    if (interaction.isChatInputCommand()) {
      const command = byName.get(interaction.commandName);
      if (command === undefined) {
        return;
      }
      await command.execute(interaction, ctx);
      return;
    }

    if (interaction.isAutocomplete()) {
      const command = byName.get(interaction.commandName);
      const focused = interaction.options.getFocused(true);
      const handler = command?.autocomplete?.[focused.name];
      if (handler === undefined) {
        await interaction.respond([]);
        return;
      }
      await handler(interaction, ctx);
    }
  };
}
