import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { MessageFlags } from "discord.js";
import type { ChatInputCommandInteraction } from "discord.js";
import { adminStatus, buildStatusButtons, buildStatusEmbed, loadGuilds, PAGES } from "../../src/commands/adminStatus.js";
import { isOperator } from "../../src/gateway/operator.js";
import { readGitCommit } from "../../src/stats/gitCommit.js";
import { aggregate } from "../../src/stats/aggregate.js";
import type { CalculatorContext } from "../../src/domain/calculator/handlers.js";
import type { LiveHosts } from "../../src/gateway/liveContext.js";

const OP = "237387841678606336";
const NOW = new Date("2026-11-18T12:00:00.000Z");

describe("isOperator", () => {
  afterEach(() => vi.unstubAllEnvs());
  it("allows a listed user, refuses outsiders, empty env and malformed ids", () => {
    expect(isOperator(OP, { ADMIN_USER_IDS: `111111111111111111, ${OP}` })).toBe(true);
    expect(isOperator("222222222222222222", { ADMIN_USER_IDS: OP })).toBe(false);
    expect(isOperator(OP, {})).toBe(false);
    expect(isOperator("abc", { ADMIN_USER_IDS: "abc" })).toBe(false);
  });
});

describe("readGitCommit", () => {
  let dir: string;
  beforeEach(() => { dir = mkdtempSync(path.join(tmpdir(), "git-")); });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));
  it("reads a branch ref", () => {
    mkdirSync(path.join(dir, ".git/refs/heads"), { recursive: true });
    writeFileSync(path.join(dir, ".git/HEAD"), "ref: refs/heads/main\n");
    writeFileSync(path.join(dir, ".git/refs/heads/main"), "abcdef1234567890\n");
    mkdirSync(path.join(dir, "a/b"), { recursive: true });
    expect(readGitCommit(path.join(dir, "a/b"))).toBe("abcdef1");
  });
  it("reads a detached HEAD", () => {
    mkdirSync(path.join(dir, ".git"));
    writeFileSync(path.join(dir, ".git/HEAD"), "1234567890abcdef\n");
    expect(readGitCommit(dir)).toBe("1234567");
  });
  it("returns unknown without .git", () => {
    expect(readGitCommit(dir)).toBe("unknown");
  });
});

const input = (n = 0, long = false) => ({
  aggregate: aggregate([], NOW),
  guilds: Array.from({ length: n }, (_, i) => ({ name: (long ? "G".repeat(90) : "Guild") + i, members: i })),
  startedAt: new Date("2026-11-18T00:00:00.000Z"), now: NOW, pingMs: 42, commit: "abcdef1",
  counts: { weapons: 1, targets: 2, vehicles: 3 },
  versions: { data: "d", calculator: "c", fuzzy: "f" },
});

describe("buildStatusEmbed pages", () => {
  it("every page renders with zero data and has its own title", () => {
    const titles = PAGES.map((p) => buildStatusEmbed(p.id, input()).toJSON().title);
    expect(new Set(titles).size).toBe(PAGES.length);
  });
  it("summary shows servers, game data, usage totals and the 7-day error count", () => {
    const text = JSON.stringify(buildStatusEmbed("summary", input(3)).toJSON());
    for (const w of ["Servers: 3", "Weapons: 1", "Commands run: 0", "Errors (7d): 0"]) expect(text).toContain(w);
  });
  it("servers page lists every server, largest first, not just five", () => {
    const d = buildStatusEmbed("servers", input(12)).toJSON().description!;
    expect(d.split("\n")).toHaveLength(12);
    expect(d.split("\n")[0]).toContain("Guild11");
  });
  it("servers page stays within the 4096 description limit with 200 long-named guilds", () => {
    const e = buildStatusEmbed("servers", input(200, true)).toJSON();
    expect(e.description!.length).toBeLessThanOrEqual(4096);
  });
  it("errors page shows errors by type", () => {
    const agg = { ...aggregate([], NOW), errorsByType: [["Exception", 4]] as [string, number][] };
    const text = JSON.stringify(buildStatusEmbed("errors", { ...input(), aggregate: agg }).toJSON());
    expect(text).toContain("Exception: 4");
  });
  it("all fields respect the 25-field and 1024-character limits", () => {
    for (const p of PAGES) {
      const f = buildStatusEmbed(p.id, input(200, true)).toJSON().fields ?? [];
      expect(f.length).toBeLessThanOrEqual(25);
      for (const x of f) expect(x.value.length).toBeLessThanOrEqual(1024);
    }
  });
});

describe("usage page layout", () => {
  const agg = {
    ...aggregate([], NOW),
    total: 4, uniqueUsers: 2,
    perCommand: { how: 1, kill: 3 },
    topWeapons: [["150mm", 3], ["Satchel", 1]] as [string, number][],
    topTargets: [["Victa", 2]] as [string, number][],
    failedLookups: [["x / y", 1]] as [string, number][],
  };
  const fields = (a = agg) => buildStatusEmbed("usage", { ...input(), aggregate: a }).toJSON().fields!;
  const byName = (n: string, a = agg) => fields(a).find((f) => f.name === n)!;

  it("has Totals, Unique users and Failed lookups as inline summary fields", () => {
    expect(byName("Totals")).toMatchObject({ value: "4 runs", inline: true });
    expect(byName("Unique users")).toMatchObject({ value: "2", inline: true });
    expect(byName("Failed lookups")).toMatchObject({ value: "1 (25.0%)", inline: true });
  });
  it("says 1 run, not 1 runs", () => {
    expect(byName("Totals", { ...agg, total: 1 }).value).toBe("1 run");
  });
  it("lists commands in an aligned code block sorted by count with share of total", () => {
    const v = byName("Commands").value;
    expect(v.startsWith("```") && v.endsWith("```")).toBe(true);
    const rows = v.split("\n").slice(1, -1);
    expect(rows[0]).toContain("kill");
    expect(rows[0]).toContain("75%");
    expect(rows[1]).toContain("how");
    expect(rows[1]).toContain("25%");
    expect(new Set(rows.map((r) => r.length)).size).toBe(1);
  });
  it("numbers the top weapons and targets in two inline columns", () => {
    expect(byName("Top weapons")).toMatchObject({ value: "1. 150mm: 3\n2. Satchel: 1", inline: true });
    expect(byName("Top targets")).toMatchObject({ value: "1. Victa: 2", inline: true });
  });
  it("shows none for empty sections and 0 runs without dividing by zero", () => {
    const empty = aggregate([], NOW);
    expect(byName("Commands", empty).value).toBe("none");
    expect(byName("Top weapons", empty).value).toBe("none");
    expect(byName("Totals", empty).value).toBe("0 runs");
    expect(byName("Failed lookups", empty).value).toBe("0");
  });
  it("keeps the commands block inside the 1024-character limit with many commands", () => {
    const many = Object.fromEntries(Array.from({ length: 200 }, (_, n) => ["command_number_" + n, 200 - n]));
    const v = byName("Commands", { ...agg, total: 20100, perCommand: many }).value;
    expect(v.length).toBeLessThanOrEqual(1024);
    expect(v.endsWith("```")).toBe(true);
  });
});

describe("buildStatusButtons", () => {
  it("has one button per page with stateless ids, highlighting the current page", () => {
    const row = buildStatusButtons("usage").toJSON();
    const ids = row.components.map((c) => (c as { custom_id: string }).custom_id);
    expect(ids).toEqual(["admin_status:summary", "admin_status:servers", "admin_status:usage", "admin_status:problems", "admin_status:errors"]);
    const styles = row.components.map((c) => (c as { style: number }).style);
    expect(styles).toEqual([2, 2, 1, 2, 2]);
  });
});

const fakeGuilds = (ids: string[], fetch = vi.fn(async ({ guild }: { guild: string }) => ({ name: `Name${guild}`, approximateMemberCount: Number(guild) }))) =>
  ({ cache: new Map(ids.map((id) => [id, { id, name: undefined, memberCount: undefined }])), fetch });

describe("loadGuilds", () => {
  it("fetches name and member count over REST because the cache has only stubs", async () => {
    const guilds = fakeGuilds(["5", "9"]);
    const out = await loadGuilds({ guilds } as never, new Map());
    expect(out).toEqual([{ name: "Name5", members: 5 }, { name: "Name9", members: 9 }]);
    expect(guilds.fetch).toHaveBeenCalledWith({ guild: "5", withCounts: true, force: true });
  });
  it("fetches each guild only once; failed fetches are retried next time", async () => {
    const cache = new Map();
    const guilds = fakeGuilds(["5", "9"]);
    await loadGuilds({ guilds } as never, cache);
    await loadGuilds({ guilds } as never, cache);
    expect(guilds.fetch).toHaveBeenCalledTimes(2);

    let fail = true;
    const flaky = fakeGuilds(["5"], vi.fn(async () => {
      if (fail) throw new Error("403");
      return { name: "Ok", approximateMemberCount: 3 };
    }));
    const c2 = new Map();
    expect((await loadGuilds({ guilds: flaky } as never, c2))[0]?.name).toBe("unknown");
    fail = false;
    expect((await loadGuilds({ guilds: flaky } as never, c2))[0]?.name).toBe("Ok");
    expect(flaky.fetch).toHaveBeenCalledTimes(2);
  });
  it("keeps the guild as unknown/0 when its fetch fails", async () => {
    const guilds = fakeGuilds(["5", "9"], vi.fn(async ({ guild }: { guild: string }) => {
      if (guild === "5") throw new Error("403");
      return { name: "Ok", approximateMemberCount: 3 };
    }));
    const out = await loadGuilds({ guilds } as never, new Map());
    expect(out).toEqual([{ name: "unknown", members: 0 }, { name: "Ok", members: 3 }]);
  });
});

function interaction(id: string) {
  return {
    user: { id },
    reply: vi.fn().mockResolvedValue(undefined),
    deferReply: vi.fn().mockResolvedValue(undefined),
    editReply: vi.fn().mockResolvedValue(undefined),
    client: { guilds: fakeGuilds(["7"]), uptime: 1000, ws: { ping: 5 } },
  };
}
const hosts = { dataHost: { get: () => ({ weapons: {}, targets: {} }), version: "d" }, calculatorHost: { version: "c" }, fuzzyHost: { version: "f" } };
const run = (i: ReturnType<typeof interaction>) =>
  adminStatus.execute(i as unknown as ChatInputCommandInteraction, { vehicleDictionary: new Map() } as unknown as CalculatorContext, hosts as unknown as LiveHosts);

describe("admin_status execute", () => {
  afterEach(() => vi.unstubAllEnvs());
  it("refuses a non-operator, ephemeral, no embed", async () => {
    vi.stubEnv("ADMIN_USER_IDS", OP);
    const i = interaction("222222222222222222");
    await run(i);
    expect(i.reply).toHaveBeenCalledWith({ content: "Not authorized for this operation.", flags: MessageFlags.Ephemeral });
  });
  it("gives the operator one ephemeral embed", async () => {
    vi.stubEnv("ADMIN_USER_IDS", OP);
    vi.stubEnv("STATS_DIR", mkdtempSync(path.join(tmpdir(), "st-")));
    const i = interaction(OP);
    await run(i);
    expect(i.deferReply).toHaveBeenCalledWith({ flags: MessageFlags.Ephemeral });
    const arg = i.editReply.mock.calls[0]![0] as { embeds: unknown[]; components: unknown[] };
    expect(arg.embeds).toHaveLength(1);
    expect(arg.components).toHaveLength(1);
  });
});

describe("admin_status buttons", () => {
  afterEach(() => vi.unstubAllEnvs());
  const press = (id: string, customId: string) => ({
    user: { id }, customId,
    reply: vi.fn().mockResolvedValue(undefined),
    deferUpdate: vi.fn().mockResolvedValue(undefined),
    editReply: vi.fn().mockResolvedValue(undefined),
    client: { guilds: fakeGuilds(["7"]), uptime: 1000, ws: { ping: 5 } },
  });
  const click = (b: ReturnType<typeof press>) =>
    adminStatus.onButton!(b as never, { vehicleDictionary: new Map() } as unknown as CalculatorContext, hosts as unknown as LiveHosts);

  it("refuses a non-operator without updating the message", async () => {
    vi.stubEnv("ADMIN_USER_IDS", OP);
    const b = press("222222222222222222", "admin_status:usage");
    await click(b);
    expect(b.reply).toHaveBeenCalledWith({ content: "Not authorized for this operation.", flags: MessageFlags.Ephemeral });
    expect(b.editReply).not.toHaveBeenCalled();
  });
  it("switches page for the operator: new embed and buttons with that page highlighted", async () => {
    vi.stubEnv("ADMIN_USER_IDS", OP);
    vi.stubEnv("STATS_DIR", mkdtempSync(path.join(tmpdir(), "st-")));
    const b = press(OP, "admin_status:problems");
    await click(b);
    expect(b.deferUpdate).toHaveBeenCalled();
    const arg = b.editReply.mock.calls[0]![0] as { embeds: { toJSON(): { title: string } }[]; components: { toJSON(): { components: { style: number }[] } }[] };
    expect(arg.embeds[0]!.toJSON().title).toContain("Problems");
    expect(arg.components[0]!.toJSON().components.map((c) => c.style)).toEqual([2, 2, 2, 1, 2]);
  });
  it("ignores an unknown page id", async () => {
    vi.stubEnv("ADMIN_USER_IDS", OP);
    const b = press(OP, "admin_status:nope");
    await click(b);
    expect(b.editReply).not.toHaveBeenCalled();
  });
});
