// Shared shape every slash command module (commands/*.ts) implements —
// bundles the discord.js command definition with its execute/autocomplete
// handlers so commandRouter.ts can dispatch generically instead of one
// hardcoded if/else chain per command (bot.py had this implicitly via
// decorators; discord.js has no decorator equivalent for a plain script).
import type { AutocompleteInteraction, ButtonInteraction, ChatInputCommandInteraction, SlashCommandBuilder } from "discord.js";
import type { CalculatorContext } from "../domain/calculator/handlers.js";
import type { LiveHosts } from "./liveContext.js";

export interface SlashCommand {
  data: SlashCommandBuilder;
  /** `hosts` gives access to the live PluginHosts themselves (not just the
   * resolved `ctx` snapshot) — only commands/adminSwap.ts actually uses it,
   * to call .swap()/.rollback(); every other command ignores the third
   * parameter, which TypeScript/JS both allow (a callback with fewer
   * declared params still satisfies a wider function type). */
  /** Options to store in the stats record instead of the raw interaction
   * options (used by /how so the free-text query is never written to disk). */
  recordedOptions?(interaction: ChatInputCommandInteraction): Record<string, string | number | boolean>;
  execute(interaction: ChatInputCommandInteraction, ctx: CalculatorContext, hosts: LiveHosts): Promise<void>;
  /** Button presses whose customId starts with "<command name>:" are routed
   * here by commandRouter.ts. Buttons carry their state in the customId, so
   * they keep working across restarts. Button presses are never recorded. */
  onButton?(interaction: ButtonInteraction, ctx: CalculatorContext, hosts: LiveHosts): Promise<void>;
  /** Keyed by option name (e.g. "target", "weapon", "weapon1") — dispatched
   * by commandRouter.ts via interaction.options.getFocused(true).name, since
   * one command can have several autocompleted options that need different
   * dictionaries (see custom_kill's weapon1/weapon2/target). */
  autocomplete?: Record<string, (interaction: AutocompleteInteraction, ctx: CalculatorContext) => Promise<void>>;
}
