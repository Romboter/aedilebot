// Shared shape every slash command module (commands/*.ts) implements —
// bundles the discord.js command definition with its execute/autocomplete
// handlers so commandRouter.ts can dispatch generically instead of one
// hardcoded if/else chain per command (bot.py had this implicitly via
// decorators; discord.js has no decorator equivalent for a plain script).
import type { AutocompleteInteraction, ChatInputCommandInteraction, SlashCommandBuilder } from "discord.js";
import type { CalculatorContext } from "../domain/calculator/handlers.js";

export interface SlashCommand {
  data: SlashCommandBuilder;
  execute(interaction: ChatInputCommandInteraction, ctx: CalculatorContext): Promise<void>;
  /** Keyed by option name (e.g. "target", "weapon", "weapon1") — dispatched
   * by commandRouter.ts via interaction.options.getFocused(true).name, since
   * one command can have several autocompleted options that need different
   * dictionaries (see custom_kill's weapon1/weapon2/target). */
  autocomplete?: Record<string, (interaction: AutocompleteInteraction, ctx: CalculatorContext) => Promise<void>>;
}
