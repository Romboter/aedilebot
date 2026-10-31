import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MessageFlags } from "discord.js";
import type { ChatInputCommandInteraction } from "discord.js";
import { adminSwap, isAuthorizedSwapOperator } from "../../src/commands/adminSwap.js";
import type { LiveHosts } from "../../src/gateway/liveContext.js";
import type { CalculatorContext } from "../../src/domain/calculator/handlers.js";

const OWNER = "123456789012345678";
const GUILD = "987654321098765432";
const OUTSIDER = "222222222222222222";

function allowOperator() {
  vi.stubEnv("ADMIN_USER_IDS", OUTSIDER + ", " + OWNER);
  vi.stubEnv("ADMIN_GUILD_ID", GUILD);
}

function hosts() {
  const makeHost = () => ({
    swap: vi.fn().mockResolvedValue({ ok: true }),
    rollback: vi.fn().mockReturnValue({ ok: true }),
    version: "v2",
  });
  const dataHost = makeHost();
  const calculatorHost = makeHost();
  const fuzzyHost = makeHost();
  const obj = {
    dataHost,
    calculatorHost,
    fuzzyHost,
    defaultPaths: {
      data: "/trusted/dist/data/dataStore.js",
      calculator: "/trusted/dist/domain/calculator/plugin.js",
      fuzzy: "/trusted/dist/domain/fuzzy/plugin.js",
    },
  };
  return obj;
}

function interaction(id = OWNER, guildId: string | null = GUILD, target = "calculator", rollback = false) {
  const obj = {
    user: { id },
    guildId,
    // Simulate a third-party server Administrator. Discord role is NOT
    // sufficient to mutate this application globally.
    memberPermissions: { has: () => true },
    options: {
      getString: vi.fn((name: string) => {
        if (name === "target") return target;
        throw new Error("Unexpected option read: " + name);
      }),
      getBoolean: vi.fn(() => rollback),
    },
    reply: vi.fn().mockResolvedValue(undefined),
    deferReply: vi.fn().mockResolvedValue(undefined),
    editReply: vi.fn().mockResolvedValue(undefined),
  };
  return obj;
}

async function invoke(i: ReturnType<typeof interaction>, h: ReturnType<typeof hosts>) {
  await adminSwap.execute(
    i as unknown as ChatInputCommandInteraction,
    {} as CalculatorContext,
    h as unknown as LiveHosts,
  );
}

describe("admin_swap authorization and safe candidate selection", () => {
  beforeEach(() => {
    vi.stubEnv("ADMIN_USER_IDS", undefined);
    vi.stubEnv("ADMIN_GUILD_ID", undefined);
    vi.spyOn(console, "info").mockImplementation(() => undefined);
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("fails closed when no trusted guild or owner IDs are configured", async () => {
    const i = interaction();
    const h = hosts();
    await invoke(i, h);
    expect(i.reply).toHaveBeenCalledWith({
      content: "Not authorized for this operation.",
      flags: MessageFlags.Ephemeral,
    });
    expect(i.deferReply).not.toHaveBeenCalled();
    expect(h.calculatorHost.swap).not.toHaveBeenCalled();
  });

  it("denies an administrator of a different guild", async () => {
    allowOperator();
    const i = interaction(OWNER, OUTSIDER);
    const h = hosts();
    await invoke(i, h);
    expect(i.reply).toHaveBeenCalled();
    expect(h.calculatorHost.swap).not.toHaveBeenCalled();
  });

  it("denies a guild administrator not present in the bot-owner allowlist", async () => {
    allowOperator();
    const i = interaction("333333333333333333");
    const h = hosts();
    await invoke(i, h);
    expect(i.reply).toHaveBeenCalled();
    expect(h.calculatorHost.rollback).not.toHaveBeenCalled();
  });

  it("only allows a configured owner within the configured guild", () => {
    allowOperator();
    expect(isAuthorizedSwapOperator(OWNER, GUILD)).toBe(true);
    expect(isAuthorizedSwapOperator(OWNER, OUTSIDER)).toBe(false);
    expect(isAuthorizedSwapOperator(OUTSIDER, GUILD)).toBe(true);
    expect(isAuthorizedSwapOperator("333333333333333333", GUILD)).toBe(false);
    expect(isAuthorizedSwapOperator(OWNER, null)).toBe(false);
    vi.stubEnv("ADMIN_GUILD_ID", "invalid");
    expect(isAuthorizedSwapOperator(OWNER, GUILD)).toBe(false);
  });

  it("loads only the fixed built-module path; never reads a user path option", async () => {
    allowOperator();
    const i = interaction();
    const h = hosts();
    await invoke(i, h);
    expect(h.calculatorHost.swap).toHaveBeenCalledExactlyOnceWith(h.defaultPaths.calculator);
    expect(i.options.getString).toHaveBeenCalledExactlyOnceWith("target", true);
    expect(i.deferReply).toHaveBeenCalledWith({ flags: MessageFlags.Ephemeral });
    expect(i.editReply).toHaveBeenCalled();
    const names = adminSwap.data.toJSON().options?.map((o) => o.name);
    expect(names).not.toContain("path");
  });

  it("refuses an invalid target before selecting a host", async () => {
    allowOperator();
    const i = interaction(OWNER, GUILD, "host");
    const h = hosts();
    await invoke(i, h);
    expect(i.reply).toHaveBeenCalledWith({ content: "Invalid swap target.", flags: MessageFlags.Ephemeral });
    expect(h.calculatorHost.swap).not.toHaveBeenCalled();
    expect(h.dataHost.swap).not.toHaveBeenCalled();
  });

  it("only calls rollback, without importing anything, for a rollback action", async () => {
    allowOperator();
    const i = interaction(OWNER, GUILD, "fuzzy", true);
    const h = hosts();
    await invoke(i, h);
    expect(h.fuzzyHost.rollback).toHaveBeenCalledOnce();
    expect(h.fuzzyHost.swap).not.toHaveBeenCalled();
  });

  it("redacts internal errors in Discord responses and writes a structured audit", async () => {
    allowOperator();
    const i = interaction();
    const h = hosts();
    h.calculatorHost.swap.mockResolvedValue({ ok: false, error: new Error("secret file /opt/service/private.mjs") });
    await invoke(i, h);
    const msg = i.editReply.mock.calls[0]?.[0] as string;
    expect(msg).toContain("failed");
    expect(msg).not.toContain("private.mjs");
    expect(console.error).toHaveBeenCalledOnce();
    const log = JSON.parse(vi.mocked(console.info).mock.calls.at(-1)?.[0] as string) as {
      event: string; actorId: string; guildId: string; action: string; target: string; outcome: string;
    };
    expect(log).toMatchObject({
      event: "admin_swap", actorId: OWNER, guildId: GUILD, action: "swap", target: "calculator", outcome: "failed",
    });
    expect(JSON.stringify(log)).not.toContain("/opt/service");
  });
});
