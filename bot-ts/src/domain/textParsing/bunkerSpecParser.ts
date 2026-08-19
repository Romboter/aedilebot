// Port of parse.py's get_bunker_spec: free-text -> BunkerSpec, or null if
// unparseable. Straight, behavior-preserving port including known quirks —
// see the comment above TIER_WORDS below.
import type { BunkerSpec } from "../calculator/bunkerMath.js";

const TIER_WORDS: Record<string, number> = {
  t1: 1,
  t2: 2,
  t3: 3,
  // These multi-word keys can never match: `words` below is whitespace-
  // tokenized before lookup, so a key containing a space can never equal a
  // single token. Only t1/t2/t3/concrete actually work. Preserved as-is —
  // this is pre-existing Python behavior, not something to silently fix.
  "tier 1": 1,
  "tier 2": 2,
  "tier 3": 3,
  concrete: 3,
};

const MOD_WORDS: Record<string, string> = {
  atg: "atg",
  at: "atg",
  rg: "rg",
  rifle: "rg",
  hg: "hg",
  howi: "hg",
  howie: "hg",
  mg: "mg",
  machinegun: "mg",
  machine: "mg",
  mgg: "mg",
  ammunition: "ammo",
  ramp: "ramp",
  med: "med",
  medical: "med",
  hospital: "med",
  howitzer: "hg",
  engine: "eng",
  sc: "sc",
  storm: "sc",
  ic: "ic",
  intel: "ic",
  intelligence: "ic",
  weather: "ws",
  weathers: "ws",
  base: "core",
  core: "core",
  storage: "ammo",
  ammo: "ammo",
  obs: "obs",
  observation: "obs",
  gen: "eng",
  generator: "eng",
  generater: "eng",
  arty: "hg",
  artillery: "hg",
  shelter: "shelter",
  uf: "fortress",
  fort: "fortress",
  underground: "fortress",
  radar: "radar",
  aerial: "radar",
  array: "radar",
  red: "red",
  green: "green",
};

const DIGITS = /^\d+$/;

export function parseBunkerSpec(input: string): BunkerSpec | null {
  const args: Record<string, number> = {};
  const inc = (key: string, amount: number): void => {
    args[key] = (args[key] ?? 0) + amount;
  };

  let words = input
    .toLowerCase()
    .replaceAll(",", " ")
    .replaceAll(";", " ")
    .replaceAll("hr", "hour")
    .replaceAll("hours", "hour")
    .split(/\s+/)
    .filter((w) => w.length > 0);

  const sizeIdx = words.indexOf("size");
  if (sizeIdx === -1) {
    return null;
  }
  if (DIGITS.test(words[sizeIdx + 1] ?? "")) {
    args.size = parseInt(words[sizeIdx + 1]!, 10);
  } else if (sizeIdx - 1 > 0 && DIGITS.test(words[sizeIdx - 1] ?? "")) {
    args.size = parseInt(words[sizeIdx - 1]!, 10);
  } else {
    return null;
  }

  const hourIdx = words.indexOf("hour");
  if (hourIdx !== -1) {
    if (hourIdx - 1 >= 0 && DIGITS.test(words[hourIdx - 1] ?? "")) {
      args.wet = parseInt(words[hourIdx - 1]!, 10);
    }
  } else {
    args.wet = 24;
  }

  let tier: number | undefined;
  for (const keyword of Object.keys(TIER_WORDS)) {
    if (words.includes(keyword)) {
      tier = TIER_WORDS[keyword];
      break;
    }
  }
  if (tier === undefined) {
    return null;
  }
  args.tier = tier;

  const withIdx = words.indexOf("with");
  words = withIdx !== -1 ? words.slice(withIdx) : words.slice(words.indexOf("size"));

  let modCount = 0;
  for (let i = 0; i < words.length; i++) {
    let word = words[i]!;
    if (!(word in MOD_WORDS) && word.endsWith("s") && word.slice(0, -1) in MOD_WORDS) {
      word = word.slice(0, -1);
    }
    if (word in MOD_WORDS && i - 1 >= 0) {
      const modKey = MOD_WORDS[word]!;
      if (DIGITS.test(words[i - 1]!)) {
        const n = parseInt(words[i - 1]!, 10);
        inc(modKey, n);
        if (word !== "green" && word !== "red") {
          modCount += n;
        }
      } else {
        inc(modKey, 1);
        if (word !== "green" && word !== "red") {
          modCount += 1;
        }
      }
    }
  }

  // "wet" isn't read via defaultdict elsewhere until it's consumed as a
  // number (getBunkerWetMultiplier/getBunkerString) — Python's defaultdict(int)
  // implicitly materializes it as 0 on first access if never set above;
  // filling it in here has the same observable effect since nothing inspects
  // "is wet present as a key" (unlike "red"/"green", checked explicitly by
  // DamageCalculator's estimation logic).
  args.wet ??= 0;

  if (modCount > args.size!) {
    return null;
  }
  return args as BunkerSpec;
}
