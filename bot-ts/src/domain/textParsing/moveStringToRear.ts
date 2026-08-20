// Port of utils.py's move_string_to_rear(): canonicalizes tier/emplacement
// phrasing (e.g. "tier 3" -> trailing "t3", "entrenched" -> trailing
// "emplaced") so alias/lookup matching treats these phrasings consistently.
// First-match-wins against an ORDERED list — preserved as-is, order matters.
// Uses replaceAll (Python's str.replace replaces every occurrence, unlike
// JS's string-pattern .replace which only replaces the first).

const MOVE_TO_REAR_STRINGS = [
  "t1",
  "t2",
  "t3",
  "unemplaced",
  "unentrenched",
  "emplaced",
  "entrenched",
  "tier 1",
  "tier 2",
  "tier 3",
  "concrete",
] as const;

const TIER_WORDS: Record<string, string> = {
  "tier 1": "t1",
  "tier 2": "t2",
  "tier 3": "t3",
  concrete: "t3",
};

export function moveStringToRear(input: string): string {
  for (const replacement of MOVE_TO_REAR_STRINGS) {
    if (!input.includes(replacement)) {
      continue;
    }
    if (replacement === "tier 1" || replacement === "tier 2" || replacement === "tier 3" || replacement === "concrete") {
      const tier = TIER_WORDS[replacement];
      return input.replaceAll(replacement, "") + " " + tier;
    }
    if (replacement === "unemplaced" || replacement === "unentrenched") {
      return input.replaceAll(replacement, "");
    }
    if (replacement === "emplaced" || replacement === "entrenched") {
      return input.replaceAll(replacement, "") + " emplaced";
    }
    // t1/t2/t3
    return input.replaceAll(replacement, "") + " " + replacement;
  }
  return input;
}
