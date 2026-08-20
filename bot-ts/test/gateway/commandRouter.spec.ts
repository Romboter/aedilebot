import { describe, expect, it, vi } from "vitest";
import type { ChatInputCommandInteraction } from "discord.js";
import { createCommandRouter } from "../../src/gateway/commandRouter.js";
import type { SlashCommand } from "../../src/gateway/command.js";
import type { LiveHosts } from "../../src/gateway/liveContext.js";
import { markOutcome } from "../../src/stats/outcome.js";
import { how } from "../../src/commands/how.js";
import type { RunInput } from "../../src/stats/recorder.js";

vi.mock("../../src/gateway/liveContext.js", () => ({ currentCalculatorContext: () => ({}) }));

function fakeRecorder() {
  const runs: RunInput[] = [];
  return { runs, record: (r: RunInput) => void runs.push(r), readAll: () => [] };
}

function interaction(name: string, data: Array<{ name: string; value: string | number | boolean }> = [], queryOption?: string) {
  return {
    isChatInputCommand: () => true,
    isAutocomplete: () => false,
    commandName: name,
    user: { id: "237387841678606336" },
    guildId: "1002992031506898954",
    options: { data, getString: () => queryOption ?? null },
  } as unknown as ChatInputCommandInteraction;
}

const cmd = (name: string, execute: SlashCommand["execute"]): SlashCommand =>
  ({ data: { name } as SlashCommand["data"], execute });

describe("command router recording", () => {
  it("records a successful run with options, guild, hashless userId handoff and timing", async () => {
    const rec = fakeRecorder();
    const route = createCommandRouter([cmd("kill", async () => {})], rec);
    await route(interaction("kill", [{ name: "weapon", value: "w" }, { name: "target", value: "t" }]), {} as LiveHosts);
    expect(rec.runs).toHaveLength(1);
    expect(rec.runs[0]).toMatchObject({
      command: "kill", guildId: "1002992031506898954", options: { weapon: "w", target: "t" },
      outcome: "ok", userId: "237387841678606336",
    });
    expect(rec.runs[0]!.ms).toBeGreaterThanOrEqual(0);
  });

  it("records not_found when a command marks it", async () => {
    const rec = fakeRecorder();
    const route = createCommandRouter([cmd("kill", async () => markOutcome("not_found", "TargetNotFoundError"))], rec);
    await route(interaction("kill"), {} as LiveHosts);
    expect(rec.runs[0]).toMatchObject({ outcome: "not_found", errorType: "TargetNotFoundError" });
  });

  it("records error and rethrows the original error when a command throws", async () => {
    const rec = fakeRecorder();
    const boom = new Error("boom");
    const route = createCommandRouter([cmd("kill", async () => { throw boom; })], rec);
    await expect(route(interaction("kill"), {} as LiveHosts)).rejects.toBe(boom);
    expect(rec.runs[0]).toMatchObject({ outcome: "error", errorType: "Error" });
  });

  it("never records admin_status", async () => {
    const rec = fakeRecorder();
    const route = createCommandRouter([cmd("admin_status", async () => {})], rec);
    await route(interaction("admin_status"), {} as LiveHosts);
    expect(rec.runs).toHaveLength(0);
  });

  it("a throwing recorder does not stop the command", async () => {
    const run = vi.fn(async () => {});
    const rec = { record: () => { throw new Error("disk"); }, readAll: () => [] };
    const route = createCommandRouter([cmd("kill", run)], rec);
    await expect(route(interaction("kill"), {} as LiveHosts)).resolves.toBeUndefined();
    expect(run).toHaveBeenCalled();
  });

  it("how records parsed weapon/target/operation, never the raw query", async () => {
    const rec = fakeRecorder();
    const route = createCommandRouter([{ ...how, execute: async () => {} }], rec);
    await route(interaction("how", [{ name: "query", value: "many mammons to kill a ghouse" }], "many mammons to kill a ghouse"), {} as LiveHosts);
    const opts = rec.runs[0]!.options;
    expect(opts).toMatchObject({ operation: "kill" });
    expect(Object.keys(opts)).not.toContain("query");
    expect(JSON.stringify(rec.runs[0])).not.toContain("many mammons to kill a ghouse");
  });

  it("how with unparseable text records no options and no raw text", async () => {
    const rec = fakeRecorder();
    const route = createCommandRouter([{ ...how, execute: async () => {} }], rec);
    await route(interaction("how", [{ name: "query", value: "gibberish zzz" }], "gibberish zzz"), {} as LiveHosts);
    expect(rec.runs[0]!.options).toEqual({});
    expect(JSON.stringify(rec.runs[0])).not.toContain("gibberish");
  });

  it("routes a button press to the owning command's onButton by customId prefix", async () => {
    const onButton = vi.fn(async () => {});
    const rec = fakeRecorder();
    const route = createCommandRouter([{ ...cmd("admin_status", async () => {}), onButton }], rec);
    const press = { isChatInputCommand: () => false, isAutocomplete: () => false, isButton: () => true, customId: "admin_status:usage" };
    await route(press as never, {} as LiveHosts);
    expect(onButton).toHaveBeenCalledOnce();
    expect(rec.runs).toHaveLength(0);
  });

  it("ignores a button whose prefix matches no command", async () => {
    const route = createCommandRouter([cmd("kill", async () => {})], fakeRecorder());
    const press = { isChatInputCommand: () => false, isAutocomplete: () => false, isButton: () => true, customId: "zzz:1" };
    await expect(route(press as never, {} as LiveHosts)).resolves.toBeUndefined();
  });
});
