import { EmbedBuilder, SlashCommandBuilder } from "discord.js";
import type { SlashCommand } from "../gateway/command.js";
import { statsheetHandler } from "../domain/calculator/handlers.js";
import { EntityNotFoundError } from "../domain/errors.js";
import { respondStatsheetAutocomplete } from "./autocompleteHandlers.js";

const THUMBNAIL_URL =
  "https://media.discordapp.net/attachments/884587111624368158/1077553561010982922/g839.png?width=570&height=498";
const EMBED_COLOR = 0x992d22;

function buildEmbed(data: Array<string | number>): EmbedBuilder {
  const embed = new EmbedBuilder()
    .setTitle(String(data[1]))
    .setColor(EMBED_COLOR)
    .setThumbnail(THUMBNAIL_URL)
    .setDescription(`Statistics sheet for ${String(data[1])}`);

  const objectType = data[0];
  if (objectType === "Weapons") {
    embed.addFields({ name: "Raw Damage", value: String(data[2]), inline: true }, { name: "Damage Type", value: String(data[3]), inline: true });
  } else if (objectType === "Structures") {
    embed.addFields(
      { name: "Raw Health", value: String(data[2]), inline: true },
      { name: "Mitigation Type", value: String(data[3]), inline: true },
      // Preserved bug from bot.py: labeled "Repair Cost" but reads data[5],
      // which is actually DecayStartHours in statsheet_handler's tuple
      // (RepairCost is data[4]) — the commented-out Decay Start/Time to
      // Decay fields in the Python original suggest the indices drifted
      // when those were disabled. Not fixed here; matches live behavior.
      { name: "Repair Cost", value: String(data[5]), inline: true },
    );
  } else if (objectType === "Vehicles" || objectType === "Tripods" || objectType === "Emplacements" || objectType === "Aircraft_Parts") {
    embed.addFields(
      { name: "Raw Health", value: String(data[2]), inline: true },
      { name: "Mitigation Type", value: String(data[3]), inline: true },
    );
    if (data[6] !== "0") {
      embed.addFields(
        { name: "Max Pen Chance", value: `${String(data[5])}%`, inline: true },
        { name: "Min Pen Chance", value: `${String(data[4])}%`, inline: true },
        { name: "Armour Health", value: String(data[6]), inline: true },
      );
    }
    if (data[7] !== "") {
      embed.addFields({ name: "Reload", value: String(data[7]), inline: true });
    }
    if (data[8] !== "") {
      embed.addFields({ name: "Main Weapon", value: String(data[8]), inline: true });
    }
    if (data[9] !== "") {
      embed.addFields({ name: "Turret Disable Chance", value: `${String(data[9])}%`, inline: true });
    }
    if (data[10] !== "") {
      embed.addFields({ name: "Tracks Disable Chance", value: `${String(data[10])}%`, inline: true });
    }
  } else if (objectType === "Multitier_structures") {
    embed.addFields(
      { name: "Raw Health", value: String(data[2]), inline: true },
      { name: "Bmat Cost", value: String(data[3]), inline: true },
      { name: "Repair Cost", value: String(data[4]), inline: true },
      { name: "Mitigation Type", value: "Tier[x]GarrisonHouse", inline: true },
    );
  } else {
    throw new EntityNotFoundError(String(objectType));
  }

  embed.setFooter({ text: "Good luck on the front!", iconURL: THUMBNAIL_URL });
  return embed;
}

export const statsheet: SlashCommand = {
  data: new SlashCommandBuilder()
    .setName("statsheet")
    .setDescription("Provides a statistics sheet for any entity in the calculator")
    .addStringOption((o) => o.setName("entity").setDescription("weapon, vehicle, or structure to look up").setRequired(true).setAutocomplete(true)) as SlashCommandBuilder,

  async execute(interaction, ctx) {
    const entity = interaction.options.getString("entity", true);
    const result = statsheetHandler(ctx, entity);
    // bot.py has no guard here: statsheet_handler's not-found path RETURNS
    // (rather than raises) an EntityNotFoundError instance, so indexing it
    // as data[1] would crash the interaction with no reply — a pre-existing
    // bug, not behavior worth reproducing (an unhandled interaction failure
    // is a worse user experience than a free-text reply would ever produce,
    // since Discord shows "This interaction failed"). Replying with the
    // error message instead is a deliberate, minimal fix.
    if (result instanceof EntityNotFoundError) {
      await interaction.reply(result.message);
      return;
    }
    await interaction.reply({ embeds: [buildEmbed(result)] });
  },

  autocomplete: {
    entity: respondStatsheetAutocomplete,
  },
};
