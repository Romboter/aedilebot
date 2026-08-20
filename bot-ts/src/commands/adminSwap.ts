// Admin trigger for Phase 3's hot-swap machinery (the plan's "admin-only
// trigger command/CLI for manual swaps"). Not in the Python original.
//
// Gated by setDefaultMemberPermissions(Administrator) — discord.js/Discord's
// own native command-permission system, rather than an in-code role/ID
// check, so guild admins can further restrict it (or a server owner can
// re-grant it to a specific role) without a code change.
import { PermissionFlagsBits, SlashCommandBuilder } from "discord.js";
import type { SlashCommand } from "../gateway/command.js";
import type { SwapTarget } from "../gateway/liveContext.js";
import { hostFor } from "../gateway/liveContext.js";

const SWAP_TARGETS: SwapTarget[] = ["data", "calculator", "fuzzy"];

export const adminSwap: SlashCommand = {
  data: new SlashCommandBuilder()
    .setName("admin_swap")
    .setDescription("Admin only: hot-swap a code/data module without restarting the bot")
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addStringOption((o) =>
      o
        .setName("target")
        .setDescription("which swappable area")
        .setRequired(true)
        .addChoices(...SWAP_TARGETS.map((t) => ({ name: t, value: t }))),
    )
    .addStringOption((o) => o.setName("path").setDescription("candidate module path (optional — defaults to the current build)"))
    .addBooleanOption((o) => o.setName("rollback").setDescription("roll back to the previous module instead of swapping")) as SlashCommandBuilder,

  async execute(interaction, _ctx, hosts) {
    const target = interaction.options.getString("target", true) as SwapTarget;
    const rollback = interaction.options.getBoolean("rollback") ?? false;
    const host = hostFor(hosts, target);

    if (rollback) {
      const result = host.rollback();
      await interaction.reply(result.ok ? `Rolled back ${target}. Now at version ${host.version}.` : `Rollback failed: ${String(result.error)}`);
      return;
    }

    const path = interaction.options.getString("path") ?? hosts.defaultPaths[target];
    const result = await host.swap(path);
    await interaction.reply(
      result.ok
        ? `Swapped ${target} to ${path}. New version: ${host.version}.`
        : `Swap of ${target} to ${path} failed — left the current module untouched. Error: ${String(result.error)}`,
    );
  },
};
