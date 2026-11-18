// Port of utils.py's move_string_to_rear(): canonicalizes tier/emplacement
// phrasing (e.g. "tier 3" -> trailing "t3", "entrenched" -> trailing
// "emplaced") so alias/lookup matching treats these phrasings consistently.
// First-match-wins against an ORDERED list — preserved as-is, order matters.
// Phrases match as whole words only, case-insensitively (upstream fix: a bare
// substring test let "t1" fire inside other words). Every occurrence is
// removed, as in Python's str.replace.

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

// Unicode-aware word boundary, matching Python's `(?<!\w)...(?!\w)`.
const PATTERNS = new Map<string, RegExp>(
  MOVE_TO_REAR_STRINGS.map((phrase) => [
    phrase,
    new RegExp(`(?<![\\p{L}\\p{N}_])${phrase.replace(" ", "\\s+")}(?![\\p{L}\\p{N}_])`, "giu"),
  ]),
);

export function moveStringToRear(input: string): string {
  for (const replacement of MOVE_TO_REAR_STRINGS) {
    const pattern = PATTERNS.get(replacement)!;
    pattern.lastIndex = 0;
    if (!pattern.test(input)) {
      continue;
    }
    const stripped = input.replace(pattern, "");
    if (replacement === "tier 1" || replacement === "tier 2" || replacement === "tier 3" || replacement === "concrete") {
      return stripped + " " + TIER_WORDS[replacement];
    }
    if (replacement === "unemplaced" || replacement === "unentrenched") {
      return stripped;
    }
    if (replacement === "emplaced" || replacement === "entrenched") {
      return stripped + " emplaced";
    }
    // t1/t2/t3
    return stripped + " " + replacement;
  }
  return input;
}
