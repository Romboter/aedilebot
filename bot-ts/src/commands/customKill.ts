import { SlashCommandBuilder } from "discord.js";
import type { SlashCommand } from "../gateway/command.js";
import { customKillHandler } from "../domain/calculator/handlers.js";
import { runCalculatorOperation } from "../gateway/errorPresenter.js";
import { respondTargetAutocomplete, respondWeaponAutocomplete } from "./autocompleteHandlers.js";

export const customKill: SlashCommand = {
  data: new SlashCommandBuilder()
    .setName("custom_kill")
    .setDescription("Calculates hits to kill a target with weapon1 first, then weapon2 for the remainder")
    .addStringOption((o) => o.setName("target").setDescription("target to kill").setRequired(true).setAutocomplete(true))
    .addStringOption((o) => o.setName("weapon1").setDescription("first weapon used").setRequired(true).setAutocomplete(true))
    .addIntegerOption((o) => o.setName("num1").setDescription("number of weapon1 hits already landed").setRequired(true))
    .addStringOption((o) => o.setName("weapon2").setDescription("second weapon to finish the kill").setRequired(true).setAutocomplete(true)) as SlashCommandBuilder,

  async execute(interaction, ctx) {
    const target = interaction.options.getString("target", true);
    const weapon1 = interaction.options.getString("weapon1", true);
    const num1 = interaction.options.getInteger("num1", true);
    const weapon2 = interaction.options.getString("weapon2", true);
    const query = `Custom_kill query: target = ${target}, weapon1 = ${weapon1}, num1 = ${num1}, weapon2 = ${weapon2}`;
    await interaction.reply(runCalculatorOperation(() => customKillHandler(ctx, weapon1, num1, weapon2, target), query));
  },

  autocomplete: {
    target: respondTargetAutocomplete,
    weapon1: respondWeaponAutocomplete,
    weapon2: respondWeaponAutocomplete,
  },
};
