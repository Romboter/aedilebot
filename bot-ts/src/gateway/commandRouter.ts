// Dispatches discord.js Interaction events to the matching SlashCommand's
// execute/autocomplete handler by command name (and, for autocomplete, by
// which option is focused) — the plain-function equivalent of bot.py's
// @client.tree.command/@x.autocomplete decorator stack.
import type { Interaction } from "discord.js";
import type { LiveHosts } from "./liveContext.js";
import { currentCalculatorContext } from "./liveContext.js";
import type { SlashCommand } from "./command.js";
import { runWithOutcome } from "../stats/outcome.js";
import type { Recorder } from "../stats/recorder.js";
import { defaultRecorder } from "../stats/recorder.js";

const UNRECORDED = new Set(["admin_status"]);

export function createCommandRouter(commands: SlashCommand[], recorder: Pick<Recorder, "record"> = defaultRecorder()) {
  const byName = new Map(commands.map((command) => [command.data.name, command]));

  return async function handleInteraction(interaction: Interaction, hosts: LiveHosts): Promise<void> {
    if (interaction.isChatInputCommand()) {
      const command = byName.get(interaction.commandName);
      if (command === undefined) {
        return;
      }
      // Resolved once per interaction, fresh from whatever's currently
      // swapped in — this is the "get() fresh per invocation" atomicity
      // contract applied at the one place every command execution passes
      // through.
      const started = performance.now();
      const result = await runWithOutcome(() =>
        command.execute(interaction, currentCalculatorContext(hosts), hosts),
      );
      if (!UNRECORDED.has(command.data.name)) {
        try {
          const options = command.recordedOptions
            ? command.recordedOptions(interaction)
            : Object.fromEntries(
                interaction.options.data.flatMap((o) =>
                  o.value === undefined ? [] : [[o.name, o.value] as const],
                ),
              );
          recorder.record({
            at: new Date().toISOString(),
            command: command.data.name,
            guildId: interaction.guildId,
            options,
            outcome: result.outcome,
            ...(result.errorType !== undefined ? { errorType: result.errorType } : {}),
            ms: Math.round(performance.now() - started),
            userId: interaction.user.id,
          });
        } catch (error) {
          console.warn(`stats: could not record ${command.data.name}: ${String(error)}`);
        }
      }
      if ("thrown" in result) {
        throw result.thrown;
      }
      return;
    }

    if (interaction.isButton()) {
      const command = byName.get(interaction.customId.split(":")[0] ?? "");
      await command?.onButton?.(interaction, currentCalculatorContext(hosts), hosts);
      return;
    }

    if (interaction.isAutocomplete()) {
      const command = byName.get(interaction.commandName);
      const focused = interaction.options.getFocused(true);
      const handler = command?.autocomplete?.[focused.name];
      if (handler === undefined) {
        await interaction.respond([]);
        return;
      }
      await handler(interaction, currentCalculatorContext(hosts));
    }
  };
}
