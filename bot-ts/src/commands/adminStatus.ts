// Operator-only health and usage report. Reads the command-run record, so it
// is deliberately not recorded itself (see gateway/commandRouter.ts).
import { ActionRowBuilder, ButtonBuilder, ButtonStyle, EmbedBuilder, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { ButtonInteraction, Client } from "discord.js";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { CalculatorContext } from "../domain/calculator/handlers.js";
import type { SlashCommand } from "../gateway/command.js";
import type { LiveHosts } from "../gateway/liveContext.js";
import { isOperator } from "../gateway/operator.js";
import type { Aggregate } from "../stats/aggregate.js";
import { aggregate } from "../stats/aggregate.js";
import { readGitCommit } from "../stats/gitCommit.js";
import { defaultRecorder } from "../stats/recorder.js";

const EMBED_COLOR = 0x992d22;
const MAX_VALUE = 1000;
const MAX_DESCRIPTION = 4000;

type GuildInfo = { name: string; members: number };

export interface StatusInput {
  aggregate: Aggregate;
  guilds: GuildInfo[];
  startedAt: Date;
  now: Date;
  pingMs: number;
  commit: string;
  counts: { weapons: number; targets: number; vehicles: number };
  versions: { data: string; calculator: string; fuzzy: string };
}

function clip(text: string): string {
  const value = text === "" ? "none" : text;
  return value.length > MAX_VALUE ? value.slice(0, MAX_VALUE - 1) + "…" : value;
}

const lines = (pairs: [string, number][]): string => pairs.map(([k, n]) => `${k}: ${n}`).join("\n");

function uptime(ms: number): string {
  const m = Math.floor(ms / 60_000);
  return `${Math.floor(m / 1440)}d ${Math.floor((m % 1440) / 60)}h ${m % 60}m`;
}

const ranked = (pairs: [string, number][]): string =>
  clip(pairs.map(([k, n], idx) => `${idx + 1}. ${k}: ${n}`).join("\n"));

/** Aligned code-block table (name, count, share), sorted by count, cut so the
 * whole fenced block stays inside Discord's 1024-character field limit. */
function commandTable(entries: [string, number][], share: (n: number) => string): string {
  if (entries.length === 0) return "none";
  const sorted = [...entries].sort((x, y) => y[1] - x[1] || x[0].localeCompare(y[0]));
  const nameWidth = Math.max(...sorted.map(([name]) => name.length));
  const countWidth = Math.max(...sorted.map(([, n]) => String(n).length));
  const rows = sorted.map(([name, n]) => `${name.padEnd(nameWidth)}  ${String(n).padStart(countWidth)}  ${share(n).padStart(4)}`);
  const kept: string[] = [];
  let size = 8; // two fences and their newlines
  for (const row of rows) {
    if (size + row.length + 1 > MAX_VALUE) break;
    kept.push(row);
    size += row.length + 1;
  }
  return "```\n" + kept.join("\n") + "\n```";
}

export type PageId = "summary" | "servers" | "usage" | "problems" | "errors";

export const PAGES: { id: PageId; label: string }[] = [
  { id: "summary", label: "Summary" },
  { id: "servers", label: "Servers" },
  { id: "usage", label: "Usage" },
  { id: "problems", label: "Problems" },
  { id: "errors", label: "Errors" },
];

const BUTTON_PREFIX = "admin_status:";

function describe(text: string): string {
  const value = text === "" ? "none" : text;
  return value.length > MAX_DESCRIPTION ? value.slice(0, MAX_DESCRIPTION - 1) + "…" : value;
}

export function buildStatusEmbed(page: PageId, i: StatusInput): EmbedBuilder {
  const a = i.aggregate;
  const label = PAGES.find((p) => p.id === page)?.label ?? page;
  const embed = new EmbedBuilder().setTitle(`Bot status: ${label}`).setColor(EMBED_COLOR).setTimestamp(i.now);
  switch (page) {
    case "summary": {
      const errors7d = a.errorsPerDay.reduce((sum, [, n]) => sum + n, 0);
      const swap = a.lastSwap
        ? `${a.lastSwap.rollback ? "rollback" : "swap"} ${a.lastSwap.outcome} at ${a.lastSwap.at}`
        : "none recorded";
      return embed.addFields(
        {
          name: "Bot",
          value: clip(
            `Servers: ${i.guilds.length}
Uptime: ${uptime(i.now.getTime() - i.startedAt.getTime())} (since ${i.startedAt.toISOString()})
Ping: ${i.pingMs} ms
Commit: ${i.commit}`,
          ),
        },
        {
          name: "Game data",
          value: clip(
            `Weapons: ${i.counts.weapons}, targets: ${i.counts.targets}, vehicles: ${i.counts.vehicles}
Loaded: data ${i.versions.data}, calculator ${i.versions.calculator}, fuzzy ${i.versions.fuzzy}
Last admin_swap: ${swap}`,
          ),
        },
        { name: "Usage", value: clip(`Commands run: ${a.total}, unique users: ${a.uniqueUsers}`) },
        { name: "Problems", value: clip(`Failed lookups: ${a.failedLookups.reduce((sum, [, n]) => sum + n, 0)}
Errors (7d): ${errors7d}`) },
      );
    }
    case "servers":
      return embed.setDescription(
        describe([...i.guilds].sort((x, y) => y.members - x.members).map((g) => `${g.name}: ${g.members}`).join("\n")),
      );
    case "usage": {
      const failed = a.failedLookups.reduce((sum, [, n]) => sum + n, 0);
      const share = (n: number): string => (a.total === 0 ? "0%" : `${Math.round((n / a.total) * 100)}%`);
      return embed.addFields(
        { name: "Totals", value: `${a.total.toLocaleString("en-US")} ${a.total === 1 ? "run" : "runs"}`, inline: true },
        { name: "Unique users", value: String(a.uniqueUsers), inline: true },
        {
          name: "Failed lookups",
          value: a.total === 0 || failed === 0 ? String(failed) : `${failed} (${((failed / a.total) * 100).toFixed(1)}%)`,
          inline: true,
        },
        { name: "Commands", value: commandTable(Object.entries(a.perCommand), share) },
        { name: "Top weapons", value: ranked(a.topWeapons), inline: true },
        { name: "Top targets", value: ranked(a.topTargets), inline: true },
      );
    }
    case "problems":
      return embed.addFields({ name: "Failed lookups (matched nothing)", value: clip(lines(a.failedLookups)) });
    case "errors":
      return embed.addFields(
        { name: "Errors per day (UTC, last 7)", value: clip(lines(a.errorsPerDay)) },
        { name: "Errors by type", value: clip(lines(a.errorsByType)) },
      );
  }
}

export function buildStatusButtons(current: PageId): ActionRowBuilder<ButtonBuilder> {
  return new ActionRowBuilder<ButtonBuilder>().addComponents(
    PAGES.map((p) =>
      new ButtonBuilder()
        .setCustomId(BUTTON_PREFIX + p.id)
        .setLabel(p.label)
        .setStyle(p.id === current ? ButtonStyle.Primary : ButtonStyle.Secondary),
    ),
  );
}

const guildCache = new Map<string, GuildInfo>();

/** With no gateway intents the guild cache holds name-less stubs, so names and
 * member counts come from one REST fetch per guild, made once per guild per
 * process and kept. ponytail: member counts go stale until restart; add a TTL
 * if that matters. Failed fetches are not cached, so they retry next time. */
export async function loadGuilds(client: Pick<Client, "guilds">, cache: Map<string, GuildInfo> = guildCache): Promise<GuildInfo[]> {
  const ids = [...client.guilds.cache.keys()];
  return Promise.all(
    ids.map(async (id): Promise<GuildInfo> => {
      const hit = cache.get(id);
      if (hit !== undefined) return hit;
      try {
        const g = await client.guilds.fetch({ guild: id, withCounts: true, force: true });
        const info: GuildInfo = { name: g.name, members: g.approximateMemberCount ?? 0 };
        cache.set(id, info);
        return info;
      } catch {
        return { name: "unknown", members: 0 };
      }
    }),
  );
}

async function gather(client: Client, ctx: CalculatorContext, hosts: LiveHosts): Promise<StatusInput> {
  const now = new Date();
  const data = hosts.dataHost.get();
  return {
    aggregate: aggregate(defaultRecorder().readAll(), now),
    guilds: await loadGuilds(client),
    startedAt: new Date(now.getTime() - (client.uptime ?? 0)),
    now,
    pingMs: client.ws.ping,
    commit: readGitCommit(path.dirname(fileURLToPath(import.meta.url))),
    counts: {
      weapons: Object.keys(data.weapons).length,
      targets: Object.keys(data.targets).length,
      vehicles: ctx.vehicleDictionary.size,
    },
    versions: { data: hosts.dataHost.version, calculator: hosts.calculatorHost.version, fuzzy: hosts.fuzzyHost.version },
  };
}

export const adminStatus: SlashCommand = {
  data: new SlashCommandBuilder()
    .setName("admin_status")
    .setDescription("Operator only: bot health and usage")
    .setDefaultMemberPermissions(0n) as SlashCommandBuilder,

  async execute(interaction, ctx, hosts) {
    if (!isOperator(interaction.user.id)) {
      await interaction.reply({ content: "Not authorized for this operation.", flags: MessageFlags.Ephemeral });
      return;
    }
    await interaction.deferReply({ flags: MessageFlags.Ephemeral });
    const input = await gather(interaction.client, ctx, hosts);
    await interaction.editReply({ embeds: [buildStatusEmbed("summary", input)], components: [buildStatusButtons("summary")] });
  },

  async onButton(interaction, ctx, hosts) {
    if (!isOperator(interaction.user.id)) {
      await interaction.reply({ content: "Not authorized for this operation.", flags: MessageFlags.Ephemeral });
      return;
    }
    const page = PAGES.find((p) => BUTTON_PREFIX + p.id === interaction.customId)?.id;
    if (page === undefined) {
      return;
    }
    await interaction.deferUpdate();
    const input = await gather(interaction.client, ctx, hosts);
    await interaction.editReply({ embeds: [buildStatusEmbed(page, input)], components: [buildStatusButtons(page)] });
  },
};
