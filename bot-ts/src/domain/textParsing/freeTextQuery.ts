// Port of bot.py's handle_response regex dispatch — the free-text
// "how many/much <weapon> to kill/disable/dehusk <target>" pattern matching
// that routes an on_message Discord message to a calculator operation.
//
// Deliberately NOT ported here: handle_response_inner's try/except ->
// user-facing-string conversion (and its error_log.txt file write). That's
// presentation/logging behavior with I/O side effects, which belongs in
// gateway/errorPresenter.ts (Phase 2) — this module stays a pure string ->
// structured-query parser, per domain/*'s zero-I/O rule. Callers pass the
// parsed { weapon, target, operation } into domain/calculator/handlers.ts
// themselves (choosing general_kill_handler vs. general_bunker_kill_handler
// etc. based on `operation`).
//
// September 2026 Python fix: split the query FIRST. For disable/dehusk,
// normalize each extracted weapon/target separately; kill/destroy deliberately
// passes the original segments through unchanged. Normalizing the entire
// message previously moved a tier name across the "to ..." boundary.
import { moveStringToRear } from "./moveStringToRear.js";

export type FreeTextOperation = "kill" | "bunker" | "disable" | "dehusk";

export interface ParsedFreeTextQuery {
  weapon: string;
  target: string;
  operation: FreeTextOperation;
}

const KILL_PATTERN = /how (?:many|much)(.*) to (?:kill|destroy) (.*)/;
const DISABLE_PATTERN = /how (?:many|much)(.*) to disable (.*)/;
const DEHUSK_PATTERN = /how (?:many|much)(.*) to dehusk (.*)/;

/** Returns null when no pattern matches (bot.py's handle_response falls off
 * the end and implicitly returns None in that case — main.message_handler
 * only replies when the result is truthy). */
export function parseFreeTextQuery(message: string): ParsedFreeTextQuery | null {
  const lower = message.toLowerCase();

  const killMatch = KILL_PATTERN.exec(lower);
  if (killMatch !== null) {
    const weapon = killMatch[1]!;
    const target = killMatch[2]!;
    return { weapon, target, operation: target.includes("size") ? "bunker" : "kill" };
  }

  const disableMatch = DISABLE_PATTERN.exec(lower);
  if (disableMatch !== null) {
    return { weapon: moveStringToRear(disableMatch[1]!), target: moveStringToRear(disableMatch[2]!), operation: "disable" };
  }

  const dehuskMatch = DEHUSK_PATTERN.exec(lower);
  if (dehuskMatch !== null) {
    return { weapon: moveStringToRear(dehuskMatch[1]!), target: moveStringToRear(dehuskMatch[2]!), operation: "dehusk" };
  }

  return null;
}
