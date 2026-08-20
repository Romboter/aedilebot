// Port of bot.py's on_ready command sync (`client.tree.sync()` + logging).
// Slash command *definitions* are never part of the hot-swap story per the
// plan — this is only ever called explicitly (on startup here; a manual
// admin trigger once Phase 3's hot-swap lands), never implicitly alongside a
// domain/data swap.
import type { Client } from "discord.js";
import type { SlashCommand } from "./command.js";

export async function syncCommands(client: Client<true>, commands: SlashCommand[]): Promise<void> {
  const synced = await client.application.commands.set(commands.map((command) => command.data.toJSON()));
  console.log(`Synced ${synced.size} commands:`);
  for (const command of synced.values()) {
    console.log(`  - ${command.name}`);
  }
}
