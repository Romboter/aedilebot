import { SlashCommandBuilder } from "discord.js";
import type { SlashCommand } from "../gateway/command.js";
import { generalKillHandler } from "../domain/calculator/handlers.js";
import { runCalculatorOperation } from "../gateway/errorPresenter.js";
import { respondTargetAutocomplete, respondWeaponAutocomplete } from "./autocompleteHandlers.js";

export const kill: SlashCommand = {
  data: new SlashCommandBuilder()
    .setName("kill")
    .setDescription("Calculates how many hits of a weapon it takes to kill a target")
    .addStringOption((o) => o.setName("target").setDescription("target to kill").setRequired(true).setAutocomplete(true))
    .addStringOption((o) => o.setName("weapon").setDescription("weapon to use").setRequired(true).setAutocomplete(true)) as SlashCommandBuilder,

  async execute(interaction, ctx) {
    const target = interaction.options.getString("target", true);
    const weapon = interaction.options.getString("weapon", true);
    const query = `kill query: target = ${target}, weapon = ${weapon}`;
    await interaction.reply(runCalculatorOperation(() => generalKillHandler(ctx, weapon, target), query));
  },

  autocomplete: {
    target: respondTargetAutocomplete,
    weapon: respondWeaponAutocomplete,
  },
};
