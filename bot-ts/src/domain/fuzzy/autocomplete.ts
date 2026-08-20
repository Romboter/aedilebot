// Fix for the live autocomplete-latency bug (see the rewrite plan's "Fuzzy
// Matching Redesign" section). Root cause, confirmed in fuzzy.py/bot.py:
// kill_autocompletion_target (and its weapon/disable/dehusk/statsheet
// siblings) did one O(n) scan to collect candidate alias KEYS
// (fuzzy_match_target_name_command), then for every one of those candidates
// re-ran a FULL single-winner fuzzy match (fuzzy_match_target_name) just to
// resolve the key back to its canonical name — even though that key came
// straight out of the alias dictionary, so dictionary.get(key) gives the
// identical answer in O(1). That redundant full rescan per candidate is the
// O(n^2) per keystroke, not the choice of fuzzy library.
//
// Fix here: exactly one O(n) pass (two only when the rare >threshold-perfect-
// ties fallback fires, matching the Python original's own tie-break — still
// not compounded per-candidate). Canonical comes straight from the map
// value.
//
// ponytail: this drops one edge case the old rescan-per-candidate code
// incidentally preserved — if two *different* alias keys are exact word-set
// permutations of each other (both score a perfect token_set_ratio against
// each other), the old code's re-match could occasionally resolve one of
// them to the *other's* canonical via its own internal tie-break, instead of
// its own dictionary value. That's a rare pre-existing data-dependent
// coincidence, not a documented behavior worth an O(n^2) to preserve — direct
// map lookup is used instead. Revisit only if real alias data is found to
// collide this way.
import * as fuzzball from "fuzzball";
import { normalize } from "../normalize.js";

export interface AutocompleteChoice {
  name: string;
  value: string;
}

const MIN_SCORE = 60;
const MAX_RESULTS = 20;

interface ScoredCandidate {
  canonical: string;
  score: number;
}

/** Single O(n) pass over `dictionary` (alias -> canonical), collecting
 * distinct canonical names whose alias key scores > 60 against the query,
 * in dictionary iteration order (not sorted by score — matches the Python
 * original's own unsorted good_score_list, not a change worth making here).
 * `perfectRescanThreshold` mirrors the small per-dictionary tie-break bot.py
 * used (5 for targets, 1 for the combined "any" dictionary, none for
 * weapons) — if more than that many aliases score a perfect 100, the whole
 * pass is redone once with token_sort_ratio instead, same as Python. */
export function autocompleteCandidates(
  query: string,
  dictionary: Map<string, string>,
  perfectRescanThreshold?: number,
): AutocompleteChoice[] {
  const name = normalize(query);
  const matches: ScoredCandidate[] = [];
  let perfectCount = 0;

  for (const [key, canonical] of dictionary) {
    const score = fuzzball.token_set_ratio(name, key);
    if (score > MIN_SCORE) {
      matches.push({ canonical, score });
      if (score === 100) {
        perfectCount++;
      }
    }
  }

  if (perfectRescanThreshold !== undefined && perfectCount > perfectRescanThreshold) {
    return dedupeCanonical(rescanByTokenSortRatio(name, dictionary));
  }
  return dedupeCanonical(matches);
}

function rescanByTokenSortRatio(name: string, dictionary: Map<string, string>): ScoredCandidate[] {
  const matches: ScoredCandidate[] = [];
  for (const [key, canonical] of dictionary) {
    const score = fuzzball.token_sort_ratio(name, key);
    if (score > MIN_SCORE) {
      matches.push({ canonical, score });
    }
  }
  return matches;
}

function dedupeCanonical(matches: ScoredCandidate[]): AutocompleteChoice[] {
  const seen = new Set<string>();
  const result: AutocompleteChoice[] = [];
  for (const { canonical } of matches) {
    if (seen.has(canonical)) {
      continue;
    }
    seen.add(canonical);
    result.push({ name: canonical, value: canonical });
    if (result.length === MAX_RESULTS) {
      break;
    }
  }
  return result;
}
