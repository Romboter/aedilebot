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

export function singularize(word: string): string {
  return pluralize.singular(word);
}
