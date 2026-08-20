import { SlashCommandBuilder } from "discord.js";
import type { SlashCommand } from "../gateway/command.js";
import { generalDehuskHandler } from "../domain/calculator/handlers.js";
import { runCalculatorOperation } from "../gateway/errorPresenter.js";
import { respondDehuskTargetAutocomplete, respondWeaponAutocomplete } from "./autocompleteHandlers.js";

export const dehusk: SlashCommand = {
  data: new SlashCommandBuilder()
    .setName("dehusk")
    .setDescription("Calculates how many hits of a weapon it takes to dehusk a target")
    .addStringOption((o) => o.setName("target").setDescription("husk to kill").setRequired(true).setAutocomplete(true))
    .addStringOption((o) => o.setName("weapon").setDescription("weapon to use").setRequired(true).setAutocomplete(true)) as SlashCommandBuilder,

  async execute(interaction, ctx) {
    const target = interaction.options.getString("target", true);
    const weapon = interaction.options.getString("weapon", true);
    const query = `dehusk query: target = ${target}, weapon = ${weapon}`;
    await interaction.reply(runCalculatorOperation(() => generalDehuskHandler(ctx, weapon, target), query));
  },

  autocomplete: {
    target: respondDehuskTargetAutocomplete,
    weapon: respondWeaponAutocomplete,
  },
};
