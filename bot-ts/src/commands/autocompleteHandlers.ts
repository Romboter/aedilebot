// Shared autocomplete handlers reused across commands — bot.py stacked the
// same @weapon.autocomplete/@target.autocomplete decorator onto multiple
// commands (e.g. kill_autocompletion_weapon served kill/disable/dehusk/
// custom_kill's weapon options); this is the same sharing, without
// decorators.
//
// Routed through ctx.fuzzy.autocompleteCandidates (not a static import) so
// autocomplete also observes a domain/fuzzy hot-swap, same reasoning as
// domain/calculator/handlers.ts's CalculatorContext.fuzzy.
import type { AutocompleteInteraction } from "discord.js";
import type { CalculatorContext } from "../domain/calculator/handlers.js";

// Perfect-score-tie rescan thresholds, ported from fuzzy.py's per-dictionary
// "_command" functions: targets rescan past 5 perfect ties, weapons never
// rescan, statsheet's combined "any" dictionary rescans past 1.
const TARGET_PERFECT_RESCAN_THRESHOLD = 5;
const ANY_PERFECT_RESCAN_THRESHOLD = 1;

export async function respondWeaponAutocomplete(interaction: AutocompleteInteraction, ctx: CalculatorContext): Promise<void> {
  const current = interaction.options.getFocused();
  if (current.length <= 1) {
    await interaction.respond([]);
    return;
  }
  await interaction.respond(ctx.fuzzy.autocompleteCandidates(current, ctx.weaponsDictionary));
}

export async function respondTargetAutocomplete(interaction: AutocompleteInteraction, ctx: CalculatorContext): Promise<void> {
  const current = interaction.options.getFocused();
  await interaction.respond(ctx.fuzzy.autocompleteCandidates(current, ctx.targetsDictionary, TARGET_PERFECT_RESCAN_THRESHOLD));
}

export async function respondDisableTargetAutocomplete(interaction: AutocompleteInteraction, ctx: CalculatorContext): Promise<void> {
  const current = interaction.options.getFocused();
  await interaction.respond(ctx.fuzzy.autocompleteCandidates(current, ctx.vehicleDictionary, TARGET_PERFECT_RESCAN_THRESHOLD));
}

export async function respondDehuskTargetAutocomplete(interaction: AutocompleteInteraction, ctx: CalculatorContext): Promise<void> {
  const current = interaction.options.getFocused();
  await interaction.respond(ctx.fuzzy.autocompleteCandidates(current, ctx.huskDictionary, TARGET_PERFECT_RESCAN_THRESHOLD));
}

export async function respondStatsheetAutocomplete(interaction: AutocompleteInteraction, ctx: CalculatorContext): Promise<void> {
  const current = interaction.options.getFocused();
  if (current.length <= 1) {
    await interaction.respond([]);
    return;
  }
  await interaction.respond(ctx.fuzzy.autocompleteCandidates(current, ctx.allDictionary, ANY_PERFECT_RESCAN_THRESHOLD));
}
