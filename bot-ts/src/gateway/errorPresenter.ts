// Port of bot.py's handle_response_inner: converts a thrown domain error (or
// unexpected error) into the user-facing reply string, plus an error-log
// side effect. This is the one piece of handle_response_inner's try/except
// chain that domain/textParsing/freeTextQuery.ts deliberately left out
// (presentation + logging, not parsing) — see its file header.
import { appendFileSync } from "node:fs";
import { EntityNotFoundError, InvalidTypeError, NoDamageError, TargetNotFoundError, WeaponNotFoundError } from "../domain/errors.js";

export type ErrorLogger = (errorClassName: string, query: string | undefined) => void;

/** Matches bot.py's log_error: appends one line to error_log.txt in the
 * process's cwd. Injectable so callers (and tests) aren't forced into real
 * file I/O — production wiring can just omit the argument. */
export const appendToErrorLogFile: ErrorLogger = (errorClassName, query) => {
  const timestamp = new Date().toISOString();
  appendFileSync("error_log.txt", `[${timestamp}] ${errorClassName}: ${query ?? ""}\n`);
};

/** Converts a thrown domain error into the reply string, logging (except for
 * the zero-damage case, which bot.py never logs) along the way. Every
 * EntityNotFoundError subtype returns `error.message` regardless of which
 * `instanceof` branch matches — Python's except chain only differs by which
 * class name gets logged (via each branch's own e.__class__.__name__), not
 * by what gets returned, since every branch calls `e.show_message()`. */
export function presentError(error: unknown, query?: string, logger: ErrorLogger = appendToErrorLogFile): string {
  if (error instanceof NoDamageError) {
    // Python checks `"does no damage to this entity" in message` and falls
    // back to a generic string otherwise — but NoDamageError's message
    // always contains that substring (it's baked into the format string),
    // so the fallback branch is unreachable; not replicated.
    return error.message;
  }
  if (error instanceof TargetNotFoundError) {
    logger(error.name, query);
    return error.message;
  }
  if (error instanceof InvalidTypeError) {
    logger(error.name, query);
    return error.message;
  }
  if (error instanceof WeaponNotFoundError) {
    logger(error.name, query);
    return error.message;
  }
  if (error instanceof EntityNotFoundError) {
    logger(error.name, query);
    return error.message;
  }
  console.error(error);
  logger("Exception", query);
  return "Inner error happened during processing of your request. Please, contact bot's devs about this.";
}
