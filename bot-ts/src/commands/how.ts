import { SlashCommandBuilder } from "discord.js";
import type { SlashCommand } from "../gateway/command.js";
import { parseFreeTextQuery } from "../domain/textParsing/freeTextQuery.js";
import { dispatchFreeTextQuery } from "../gateway/freeTextDispatch.js";

const NO_MATCH_REPLY =
  "I couldn't parse that — try `/how many <weapon> to kill <target>` " +
  "(also works with much/destroy/disable/dehusk).";

export const how: SlashCommand = {
  data: new SlashCommandBuilder()
    .setName("how")
    .setDescription("Same as the free-text prompt, minus typing \"how\" — e.g. \"many mammons to kill a ghouse\"")
    .addStringOption((o) =>
      o
        .setName("query")
        .setDescription('e.g. "many mammons to kill a ghouse"')
        .setRequired(true),
    ) as SlashCommandBuilder,

  async execute(interaction, ctx) {
    const query = interaction.options.getString("query", true);
    // The command name IS "how" — the user only supplies what comes after
    // it, so "how " is implied and prepended before reusing the exact same
    // free-text parser on_message uses.
    const parsed = parseFreeTextQuery(`how ${query}`);
    if (parsed === null) {
      await interaction.reply(NO_MATCH_REPLY);
      return;
    }
    await interaction.reply(dispatchFreeTextQuery(ctx, parsed, `how ${query}`));
  },
};
