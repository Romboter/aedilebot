// Privileged, process-wide administrative operation. Discord guild
// Administrator permission alone is NOT authorization to modify this bot:
// all installed guilds share one running PluginHost and data snapshot.
import { MessageFlags, SlashCommandBuilder } from "discord.js";
import type { ChatInputCommandInteraction } from "discord.js";
import type { SlashCommand } from "../gateway/command.js";
import type { SwapTarget } from "../gateway/liveContext.js";
import { hostFor } from "../gateway/liveContext.js";

const SWAP_TARGETS: SwapTarget[] = ["data", "calculator", "fuzzy"];
const SNOWFLAKE = /^\d{17,20}$/;

/** Fail closed unless both the user and guild are explicitly allowlisted.
 * Reads env vars on invocation to avoid caching a stale allowlist; the
 * process .env file is loaded once at startup by config/env.ts. */
export function isAuthorizedSwapOperator(
  userId: string,
  guildId: string | null,
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  const trustedGuild = env.ADMIN_GUILD_ID?.trim();
  if (!trustedGuild || !SNOWFLAKE.test(trustedGuild) || guildId !== trustedGuild) {
    return false;
  }
  const owners = (env.ADMIN_USER_IDS ?? "").split(/[\s,;]+/).filter((id) => SNOWFLAKE.test(id));
  return owners.includes(userId);
}

function audit(
  interaction: Pick<ChatInputCommandInteraction, "user" | "guildId">,
  action: string,
  target: string,
  outcome: string,
  version?: string,
): void {
  // Structured audit deliberately excludes full file paths, tokens,
  // supplied option values other than target, and raw exception details.
  console.info(JSON.stringify({
    event: "admin_swap",
    at: new Date().toISOString(),
    actorId: interaction.user.id,
    guildId: interaction.guildId,
    action,
    target,
    outcome,
    ...(version ? { version } : {}),
  }));
}

export const adminSwap: SlashCommand = {
  data: new SlashCommandBuilder()
    .setName("admin_swap")
    .setDescription("Trusted bot operators: reload a module or roll it back")
    // Disabled for ordinary guild members until an operator enables it in
    // the trusted guild. The runtime user+guild check is the real gate.
    .setDefaultMemberPermissions(0n)
    .addStringOption((o) =>
      o
        .setName("target")
        .setDescription("which swappable area")
        .setRequired(true)
        .addChoices(...SWAP_TARGETS.map((t) => ({ name: t, value: t }))),
    )
    // No arbitrary filesystem path is accepted from a Discord interaction.
    // Only known built module entry points from createLiveHosts() are used.
    .addBooleanOption((o) => o.setName("rollback").setDescription("roll back to the previous module instead of swapping")) as SlashCommandBuilder,

  async execute(interaction, _ctx, hosts) {
    if (!isAuthorizedSwapOperator(interaction.user.id, interaction.guildId)) {
      audit(interaction, "denied", "none", "unauthorized");
      await interaction.reply({ content: "Not authorized for this operation.", flags: MessageFlags.Ephemeral });
      return;
    }

    const inputTarget = interaction.options.getString("target", true);
    const target = SWAP_TARGETS.find((value) => value === inputTarget);
    if (target === undefined) {
      audit(interaction, "denied", "invalid", "invalid_target");
      await interaction.reply({ content: "Invalid swap target.", flags: MessageFlags.Ephemeral });
      return;
    }

    const rollback = interaction.options.getBoolean("rollback") ?? false;
    const action = rollback ? "rollback" : "swap";
    const host = hostFor(hosts, target);

    // Staging an entire compiled module graph may take longer than Discord's
    // 3-second interaction deadline. Acknowledge before starting any I/O.
    await interaction.deferReply({ flags: MessageFlags.Ephemeral });

    const result = rollback
      ? host.rollback()
      : await host.swap(hosts.defaultPaths[target]);

    if (result.ok) {
      audit(interaction, action, target, "ok", host.version);
      await interaction.editReply(
        rollback ? "Rolled back " + target + ". Version: " + host.version + "."
          : "Swapped " + target + ". Version: " + host.version + ".",
      );
    } else {
      audit(interaction, action, target, "failed", host.version);
      // Errors can contain server-side absolute paths. Log details only on
      // the operator's server, never in replies to a Discord interaction.
      console.error("admin_swap " + action + " failed for " + target, result.error);
      await interaction.editReply("The " + target + " " + action + " failed; the current module was not changed.");
    }
  },
};
