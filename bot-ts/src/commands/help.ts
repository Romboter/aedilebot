import { EmbedBuilder, SlashCommandBuilder } from "discord.js";
import type { SlashCommand } from "../gateway/command.js";

const THUMBNAIL_URL =
  "https://media.discordapp.net/attachments/884587111624368158/1077553561010982922/g839.png?width=570&height=498";
const EMBED_COLOR = 0x992d22;

export const help: SlashCommand = {
  data: new SlashCommandBuilder().setName("help").setDescription("Provides you with this message! How neat is that?") as SlashCommandBuilder,

  async execute(interaction) {
    const embed = new EmbedBuilder()
      .setTitle("__**Help and Commands**__")
      .setDescription("Welcome to the help section. Here you will be provided with a description of how the bot works and its commands.\n")
      .setColor(EMBED_COLOR)
      .setTimestamp()
      .setThumbnail(THUMBNAIL_URL)
      .addFields(
        { name: "Version", value: "0.8.66 (Up to date with foxhole U66)", inline: false },
        { name: "/help", value: "Provides you with this message! How neat is that?", inline: false },
        {
          name: "/statsheet [entity]",
          value: "Provides you with a statistics sheet of any entity in the calculator",
          inline: false,
        },
        {
          name: "/kill [target] [weapon]",
          value: "Fulfills the same purpose as the prompt below with the help of autocomplete.",
          inline: false,
        },
        {
          name: "/bunker_kill",
          value:
            "Specify the bunker island you want to kill with detailed parameters. (If a modification is not an option, it means it has the same stat as a blank bunker such as engine room)",
          inline: false,
        },
        {
          name: "**Damage Calculator Prompt**",
          value:
            "``How much|many [weapon] to destroy|kill|disable [target]``\nHere are some examples to try:\n\nHow much 150mm to kill Patridia?\nHow many satchels to kill t3 bunker core husk?\nHow many 68mm to disable HTD?\nHow many satchels to kill Victa?\nHow much 40mm to destroy bt pad?",
          inline: false,
        },
      )
      .setFooter({ text: "Good luck on the front!", iconURL: THUMBNAIL_URL });

    await interaction.reply({ embeds: [embed] });
  },
};
