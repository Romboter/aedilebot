import type { SlashCommand } from "../gateway/command.js";
import { bunkerKill } from "./bunkerKill.js";
import { customKill } from "./customKill.js";
import { dehusk } from "./dehusk.js";
import { disable } from "./disable.js";
import { help } from "./help.js";
import { kill } from "./kill.js";
import { statsheet } from "./statsheet.js";

// One entry per bot.py `@client.tree.command`.
export const commands: SlashCommand[] = [help, kill, disable, dehusk, customKill, bunkerKill, statsheet];
