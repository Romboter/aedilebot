import { SlashCommandBuilder } from "discord.js";
import type { SlashCommand } from "../gateway/command.js";
import { commandBunkerKillHandler } from "../domain/calculator/handlers.js";
import type { BunkerSpec } from "../domain/calculator/bunkerMath.js";
import { runCalculatorOperation } from "../gateway/errorPresenter.js";
import { respondWeaponAutocomplete } from "./autocompleteHandlers.js";

// Optional-modification integer options, ported 1:1 from bot.py's bunker_kill
// command (green_dots/red_dots default -1 = "estimate me"; every
// modification count defaults 0; wet defaults 24 = fully dry).
const MODIFICATION_OPTIONS: Array<[name: string, description: string]> = [
  ["rg", "rifle garrison number (Optional)"],
  ["mg", "machine gun garrison number (Optional)"],
  ["atg", "anti-tank garrison number (Optional)"],
  ["howi", "howitzer garrison number (Optional)"],
  ["shelter", "arty shelter number (Optional)"],
  ["obs", "observation bunker number (Optional)"],
  ["core", "bunker core number (Optional)"],
  ["ic", "intelligence center number (Optional)"],
  ["sc", "storm cannon number (Optional)"],
  ["ws", "weather station number (Optional)"],
  ["fortress", "underground fortress number (Optional)"],
  ["radar", "radar array number (Optional)"],
];

const builder = new SlashCommandBuilder()
  .setName("bunker_kill")
  .setDescription("Calculates hits to kill a bunker island with the given specification")
  .addStringOption((o) => o.setName("weapon").setDescription("weapon you are using to kill the bunker").setRequired(true).setAutocomplete(true))
  .addIntegerOption((o) =>
    o.setName("total_size").setDescription("total size of the bunker (including all the garrisons and blanks)").setRequired(true),
  )
  .addIntegerOption((o) =>
    o
      .setName("tier")
      .setDescription("tier of the bunker")
      .setRequired(true)
      .addChoices({ name: "Tier 1", value: 1 }, { name: "Tier 2", value: 2 }, { name: "Tier 3", value: 3 }),
  )
  .addIntegerOption((o) =>
    o.setName("green_dots").setDescription("number of bunker edges that is not exposed (Optional, will be estimated if not specified)"),
  )
  .addIntegerOption((o) =>
    o.setName("red_dots").setDescription("number of bunker edges exposed on the outer perimeter (Optional, will be estimated if not specified)"),
  );
for (const [name, description] of MODIFICATION_OPTIONS) {
  builder.addIntegerOption((o) => o.setName(name).setDescription(description));
}
builder.addIntegerOption((o) => o.setName("wet").setDescription("hours since the bunker has been upgraded to T3 (Optional)"));

export const bunkerKill: SlashCommand = {
  data: builder as SlashCommandBuilder,

  async execute(interaction, ctx) {
    const weapon = interaction.options.getString("weapon", true);
    const bunkerSpec: BunkerSpec = {
      size: interaction.options.getInteger("total_size", true),
      tier: interaction.options.getInteger("tier", true),
      green: interaction.options.getInteger("green_dots") ?? -1,
      red: interaction.options.getInteger("red_dots") ?? -1,
      rg: interaction.options.getInteger("rg") ?? 0,
      mg: interaction.options.getInteger("mg") ?? 0,
      atg: interaction.options.getInteger("atg") ?? 0,
      hg: interaction.options.getInteger("howi") ?? 0,
      shelter: interaction.options.getInteger("shelter") ?? 0,
      obs: interaction.options.getInteger("obs") ?? 0,
      core: interaction.options.getInteger("core") ?? 0,
      ic: interaction.options.getInteger("ic") ?? 0,
      sc: interaction.options.getInteger("sc") ?? 0,
      ws: interaction.options.getInteger("ws") ?? 0,
      fortress: interaction.options.getInteger("fortress") ?? 0,
      radar: interaction.options.getInteger("radar") ?? 0,
      wet: interaction.options.getInteger("wet") ?? 24,
    };
    await interaction.reply(
      runCalculatorOperation(() => commandBunkerKillHandler(ctx, weapon, bunkerSpec), `bunker_kill query: weapon = ${weapon}`),
    );
  },

  autocomplete: {
    weapon: respondWeaponAutocomplete,
  },
};
