// Port of main.message_handler + bot.py's on_message: free-text
// "how many/much X to kill/disable/dehusk Y" parsing via
// domain/textParsing/freeTextQuery.ts, dispatched to the matching
// domain/calculator/handlers.ts function, replying only when a pattern
// matched (mirrors bot.handle_response's implicit `None` return on no match
// -> `if response:` guard in main.message_handler).
import type { Message } from "discord.js";
import type { CalculatorContext } from "../domain/calculator/handlers.js";
import {
  generalBunkerKillHandler,
  generalDehuskHandler,
  generalDisableHandler,
  generalKillHandler,
} from "../domain/calculator/handlers.js";
import { parseFreeTextQuery } from "../domain/textParsing/freeTextQuery.js";
import { runCalculatorOperation } from "./errorPresenter.js";

function runParsedQuery(
  ctx: CalculatorContext,
  parsed: NonNullable<ReturnType<typeof parseFreeTextQuery>>,
  query: string,
): string {
  return runCalculatorOperation(() => {
    switch (parsed.operation) {
      case "kill":
        return generalKillHandler(ctx, parsed.weapon, parsed.target);
      case "disable":
        return generalDisableHandler(ctx, parsed.weapon, parsed.target);
      case "dehusk":
        return generalDehuskHandler(ctx, parsed.weapon, parsed.target);
      case "bunker":
        return generalBunkerKillHandler(ctx, parsed.weapon, parsed.target);
    }
  }, query);
}

export function createMessageListener(ctx: CalculatorContext, botUserId: string) {
  return async function handleMessage(message: Message): Promise<void> {
    if (message.author.id === botUserId) {
      return;
    }
    const parsed = parseFreeTextQuery(message.content);
    if (parsed === null) {
      return;
    }
    const reply = runParsedQuery(ctx, parsed, message.content);
    await message.reply({ content: reply, allowedMentions: { repliedUser: false } });
  };
}
