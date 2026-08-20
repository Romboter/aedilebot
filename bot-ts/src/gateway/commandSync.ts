// Port of bot.py's on_ready command sync (`client.tree.sync()` + logging).
// Slash command *definitions* are never part of the hot-swap story per the
// plan — this is only ever called explicitly (on startup here; a manual
// admin trigger once Phase 3's hot-swap lands), never implicitly alongside a
// domain/data swap.
import type { Client } from "discord.js";
import type { SlashCommand } from "./command.js";

/** Global registration (no `guildId`) can take up to an hour to propagate on
 * Discord's side — pass `guildId` to register to one guild instead, which
 * updates near-instantly. For fast iteration during dev-server testing only;
 * production wants global commands (see config/env.ts's TEST_GUILD_ID). */
export async function syncCommands(client: Client<true>, commands: SlashCommand[], guildId?: string): Promise<void> {
  const body = commands.map((command) => command.data.toJSON());
  const synced = guildId === undefined ? await client.application.commands.set(body) : await client.application.commands.set(body, guildId);
  console.log(`Synced ${synced.size} commands${guildId ? ` to guild ${guildId}` : ""}:`);
  for (const command of synced.values()) {
    console.log(`  - ${command.name}`);
  }
}
