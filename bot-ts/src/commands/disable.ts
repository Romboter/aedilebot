import { SlashCommandBuilder } from "discord.js";
import type { SlashCommand } from "../gateway/command.js";
import { generalDisableHandler } from "../domain/calculator/handlers.js";
import { runCalculatorOperation } from "../gateway/errorPresenter.js";
import { respondDisableTargetAutocomplete, respondWeaponAutocomplete } from "./autocompleteHandlers.js";

export const disable: SlashCommand = {
  data: new SlashCommandBuilder()
    .setName("disable")
    .setDescription("Calculates how many hits of a weapon it takes to disable a vehicle")
    .addStringOption((o) => o.setName("target").setDescription("vehicle to disable").setRequired(true).setAutocomplete(true))
    .addStringOption((o) => o.setName("weapon").setDescription("weapon to use").setRequired(true).setAutocomplete(true)) as SlashCommandBuilder,

  async execute(interaction, ctx) {
    const target = interaction.options.getString("target", true);
    const weapon = interaction.options.getString("weapon", true);
    const query = `disable query: target = ${target}, weapon = ${weapon}`;
    await interaction.reply(runCalculatorOperation(() => generalDisableHandler(ctx, weapon, target), query));
  },

  autocomplete: {
    target: respondDisableTargetAutocomplete,
    weapon: respondWeaponAutocomplete,
  },
};
