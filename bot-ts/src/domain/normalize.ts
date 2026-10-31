// Port of utils.py's normalize()/singularize(): strip punctuation, lowercase,
// collapse whitespace, drop a leading "a"/"an"/"the", singularize each word.
// Used to build alias -> canonical-name lookups (data/aliasIndex.ts) so
// slang/typo'd user input matches consistently against the same normalized
// key space the alias index was built with.
import pluralize from "pluralize";

const STOPWORDS = new Set(["a", "an", "the"]);

// Python's regex `\w` is Unicode-aware by default (matches accented letters
// found in Foxhole names), unlike JS's ASCII-only `\w` — needs \p{L}/\p{N}.
const NON_WORD_OR_SPACE = /[^\p{L}\p{N}_\s]/gu;
const EXTRA_WHITESPACE = /\s+/g;

// Python used @lru_cache(maxsize=128); the real alias vocabulary here is a
// small, static, startup-loaded set (hundreds of strings at most), so a
// plain unbounded cache is used instead of reimplementing LRU eviction —
// nothing about this workload can grow unbounded at runtime.
const cache = new Map<string, string>();

export function normalize(text: string): string {
  const cached = cache.get(text);
  if (cached !== undefined) {
    return cached;
  }

  let cleaned = text.toLowerCase().trim().replace(NON_WORD_OR_SPACE, "");
  cleaned = cleaned.replace(EXTRA_WHITESPACE, " ");

  let words = cleaned.length > 0 ? cleaned.split(" ") : [];
  if (words.length > 0 && STOPWORDS.has(words[0]!)) {
    words = words.slice(1);
  }
  const result = words.map(singularize).join(" ");

  cache.set(text, result);
  return result;
}

// Python's inflect.singular_noun() is more aggressive than the `pluralize`
// package: for a word it doesn't recognize (many proper nouns/technical
// terms — "Daedalus", "bus", "Icarus"...), its fallback naively
// strips a trailing "s" rather than leaving the word alone. `pluralize`
// leaves such words unchanged instead. Verified empirically against every
// distinct word (1531, including town/relic names merged in from
// Locations.csv) appearing in the actual game data: pluralize.singular alone
// diverges from inflect on this pattern — replicated here as a fallback.
//
// Some words ending in "s" are left unchanged by Python inflect 7.6.0,
// including common nouns and compounds/proper names. This exception set is
// measured against the 1531 real-game-data vocabulary fixtures, NOT guessed.
// inflect 7.6 changed six entries versus the older local Python environment;
// pin the fixture generator's inflect version to keep parity reproducible.
// Other words such as "crossroads"/"downs"/"barracks" still lose their "s".
const INFLECT_INVARIANT_NOUNS = new Set([
  "gallows", "headquarters", "class", "fortress", "mass",
  "ornitierclass", "pass", "sess",
]);

export function singularize(word: string): string {
  if (INFLECT_INVARIANT_NOUNS.has(word)) {
    return word;
  }
  const base = pluralize.singular(word);
  if (base !== word) {
    return base;
  }
  if (word.length > 1 && word.endsWith("s")) {
    return word.slice(0, -1);
  }
  return word;
}
