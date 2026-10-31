"""Generates golden regression fixtures by running the current Python calculator
against a curated list of cases. Output feeds the TypeScript rewrite's parity
tests (test/fixtures/calculator-fixtures.json) so behavior can be verified
identical before/after the port. Run from the repo root:

    venv/Scripts/python.exe scripts/generate_fixtures.py
"""
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import bot
import calculator
import fuzzy
import parse
import utils

# (case id, operation, args-for-handler, kwargs)
CASES = [
    # --- general_kill_handler: one per Target ObjectType ---
    ("kill_vehicle", "kill", ("40mm", "40-250 “Alekto” Heavy Cannon")),
    ("kill_structure", "kill", ("150mm", "Border base")),
    ("kill_emplacement", "kill", ("68mm", "20mm Anti Infantry Flak Gun (EMG) (Emplaced)")),
    ("kill_tripod", "kill", ("150mm", "Infantry Support Gun (ISG)")),
    ("kill_aircraft_part", "kill", ("40mm", "V-1 Tzykalia Engine")),
    ("kill_multitier", "kill", ("150mm", "Safe House")),

    # --- impact-fuse low-roll adjustment (weapon Dev Name in the hardcoded list
    # -> output becomes a "min to max" range instead of a single number) ---
    ("kill_impact_fuse_range", "kill", ("RPG", "40-250 “Alekto” Heavy Cannon")),

    # --- location-name resolution (town/relic bases via Locations.csv merge) ---
    # First location alphabetically for each mapped type; adjust if these don't
    # resolve for your current Locations.csv contents.

    # --- disable: valid vehicle, and invalid-type error path ---
    ("disable_vehicle", "disable", ("40mm", "40-250 “Alekto” Heavy Cannon")),
    ("disable_invalid_type", "disable", ("40mm", "Border base")),

    # --- dehusk ---
    ("dehusk_structure", "dehusk", ("150mm", "Power Plant Husk")),

    # --- custom_kill: two-weapon sequential, incl. weapon1-alone-kills short circuit ---
    ("custom_kill_needs_both", "custom_kill", ("7.62mm", 1, "150mm", "40-250 “Alekto” Heavy Cannon")),
    ("custom_kill_weapon1_alone_kills", "custom_kill", ("300mm", 5, "7.62mm", "Border base")),

    # --- bunker kill: direct structured spec (bypasses free-text parsing) ---
    ("bunker_kill_basic", "bunker_direct", ("Tremola Grenade GPb-1", {
        "size": 15, "tier": 3, "green": -1, "red": -1,
        "rg": 0, "mg": 2, "atg": 3, "hg": 3, "shelter": 0, "obs": 0,
        "core": 0, "ic": 0, "sc": 0, "ws": 0, "fortress": 0, "radar": 0,
        "wet": 24,
    })),
    ("bunker_kill_wet_and_shelter", "bunker_direct", ("Tremola Grenade GPb-1", {
        "size": 10, "tier": 2, "green": -1, "red": -1,
        "rg": 0, "mg": 0, "atg": 5, "hg": 0, "shelter": 2, "obs": 0,
        "core": 0, "ic": 0, "sc": 0, "ws": 0, "fortress": 0, "radar": 0,
        "wet": 6,
    })),
    ("bunker_kill_explicit_red_green", "bunker_direct", ("300mm", {
        "size": 20, "tier": 3, "green": 30, "red": 20,
        "rg": 0, "mg": 0, "atg": 0, "hg": 0, "shelter": 0, "obs": 0,
        "core": 1, "ic": 0, "sc": 0, "ws": 0, "fortress": 0, "radar": 0,
        "wet": 24,
    })),

    # --- bunker kill: via free-text parser (exercises get_bunker_spec too) ---
    ("bunker_kill_freetext", "bunker_freetext", (
        "Tremola Grenade GPb-1",
        # NOTE: parse.get_bunker_spec's tier_words dict has multi-word keys like
        # "tier 3", but the input is whitespace-tokenized before matching, so a
        # multi-word key can never equal a single token - only "t1"/"t2"/"t3"/
        # "concrete" actually work today. Preserved as-is (pre-existing behavior,
        # not something to silently fix in this fixture); the TS port should
        # replicate this exact quirk unless the team decides to fix it deliberately.
        "size 15 t3 bunker with 2 mg 3 atg 3 howi 1 ramp",
    )),

    # --- statsheet: one per ObjectType + a weapon ---
    ("statsheet_weapon", "statsheet", ("40mm",)),
    ("statsheet_vehicle", "statsheet", ("40-250 “Alekto” Heavy Cannon",)),
    ("statsheet_structure", "statsheet", ("Border base",)),
    ("statsheet_multitier", "statsheet", ("Safe House",)),

    # --- easter egg ---
    ("easter_egg", "kill", ("Watch Tower", "Scout Plane")),

    # --- error paths ---
    ("error_zero_damage", "kill", ("7.62mm", "DAE 3b-2 “Hades Net” (Unemplaced)")),
    ("error_weapon_not_found", "kill", ("totally-not-a-real-weapon-xyz", "Border base")),
    ("error_target_not_found", "kill", ("40mm", "totally-not-a-real-target-xyz")),
]


def run_case(operation, args):
    if operation == "kill":
        return calculator.general_kill_handler(*args)
    if operation == "disable":
        return calculator.general_disable_handler(*args)
    if operation == "dehusk":
        return calculator.general_dehusk_handler(*args)
    if operation == "custom_kill":
        return calculator.custom_kill_handler(*args)
    if operation == "bunker_direct":
        weapon, bunker_spec = args
        return calculator.command_bunker_kill_handler(weapon, bunker_spec)
    if operation == "bunker_freetext":
        weapon, freetext = args
        return calculator.general_bunker_kill_handler(weapon, freetext)
    if operation == "statsheet":
        return calculator.statsheet_handler(*args)
    raise ValueError(f"unknown operation {operation}")


# --- fuzzy matcher parity: queries (typos/slang/partial) drawn from real alias
# data -> expected canonical name. Proves the O(n^2)->O(n) TS rewrite of the
# autocomplete scan doesn't change WHICH result wins on ties, only speed.
FUZZY_CASES = [
    ("fuzzy_weapon_exact_alias", "weapon", "silverhand"),          # slang for 40mm
    ("fuzzy_weapon_typo", "weapon", "silverhnad"),                 # transposed letters
    ("fuzzy_weapon_partial", "weapon", "150"),
    ("fuzzy_target_slang", "target", "hades net"),
    ("fuzzy_target_typo", "target", "boarder base"),               # extra letter
    ("fuzzy_target_partial_multiword", "target", "alekto cannon"),
    ("fuzzy_husk_alias", "husk", "power plant husk"),
    ("fuzzy_vehicle_only", "vehicle", "alekto"),
]


def run_fuzzy_case(kind, query):
    if kind == "weapon":
        return fuzzy.fuzzy_match_weapon_name(query)
    if kind == "target":
        name, _tokens = fuzzy.fuzzy_match_target_name(query)
        return name
    if kind == "husk":
        name, _tokens = fuzzy.fuzzy_match_target_name(query, parse.husk_dictionary)
        return name
    if kind == "vehicle":
        name, _tokens = fuzzy.fuzzy_match_target_name(query, parse.vehicle_dictionary)
        return name
    raise ValueError(f"unknown fuzzy kind {kind}")


# --- free-text query dispatch: bot.handle_response's regex routing, factored
# out (line-for-line copy of its dispatch logic) so it can run without a full
# calculator round-trip - only the (weapon, target, operation) extraction is
# under test here, not calculator handler execution. Ground truth for
# domain/textParsing/freeTextQuery.ts.
def parse_free_text_query(message):
    p_message = message.lower()
    token_pair = re.findall(
        "how (many|much)(.*) to (kill|destroy) (.*)",
        p_message,
    )
    if len(token_pair) >= 1:
        weapon, target = token_pair[0][1], token_pair[0][3]
        if "size" in target:
            return {"weapon": weapon, "target": target, "operation": "bunker"}
        return {"weapon": weapon, "target": target, "operation": "kill"}

    token_pair = re.findall("how (many|much)(.*) to disable (.*)", p_message)
    if len(token_pair) >= 1:
        weapon, target = token_pair[0][1], token_pair[0][2]
        return {"weapon": utils.move_string_to_rear(weapon), "target": utils.move_string_to_rear(target), "operation": "disable"}

    token_pair = re.findall(
        "how (many|much)(.*) to dehusk (.*)",
        p_message,
    )
    if len(token_pair) >= 1:
        weapon, target = token_pair[0][1], token_pair[0][2]
        return {"weapon": utils.move_string_to_rear(weapon), "target": utils.move_string_to_rear(target), "operation": "dehusk"}

    return None


FREETEXT_CASES = [
    "How many 40mm to kill Border base",
    "how much 150mm to destroy a Safe House",
    "How many 68mm to disable HTD",
    "how many satchels to dehusk core husk",
    "How many tremola to kill a size 15 t3 bunker with 2 mg 3 atg 3 howi 1 ramp",
    "How MUCH 40mm to KILL entrenched bb 3x2",
    "hello world, this does not match anything",
    "how many 40mm to kill tier 3 trench",
    # Regression: never move the weapon's tier to the target side.
    "how many tier 3 atg to kill border base",
    # Disable/dehusk normalize each captured segment, not the whole query.
    "how many tier 3 atg to disable tier 2 tank",
    "how many tier 3 atg to dehusk concrete core husk",
]


def main():
    results = []
    for case_id, operation, args in CASES:
        # deep-copy args for the recorded "input" BEFORE running the case:
        # command_bunker_kill_handler/general_bunker_kill_handler mutate the
        # bunker_spec dict in place (DamageCalculator's red/green estimation),
        # so recording `args` by reference after run_case() would silently
        # capture post-mutation values instead of what was actually passed in.
        entry = {"id": case_id, "operation": operation, "input": copy.deepcopy(args)}
        try:
            output = run_case(operation, args)
            # statsheet_handler returns tuples of raw field values, everything
            # else returns either a formatted string or an EntityNotFoundError
            # instance it constructed instead of raising (see calculator.py's
            # bare except -> return bot.EntityNotFoundError(entity_name)).
            if isinstance(output, bot.EntityNotFoundError):
                entry["error"] = type(output).__name__
                entry["message"] = output.show_message()
            elif isinstance(output, tuple):
                entry["output"] = list(output)
            else:
                entry["output"] = output
        except bot.EntityNotFoundError as e:
            entry["error"] = type(e).__name__
            entry["message"] = e.show_message()
        except ZeroDivisionError as e:
            entry["error"] = "ZeroDivisionError"
            entry["message"] = str(e)
        except Exception as e:
            entry["error"] = type(e).__name__
            entry["message"] = str(e)
        results.append(entry)
        status = "error=" + entry["error"] if "error" in entry else "ok"
        print(f"{case_id}: {status}")

    out_path = os.path.join(os.path.dirname(__file__), "..", "test", "fixtures", "calculator-fixtures.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {len(results)} fixtures to {out_path}")

    fuzzy_results = []
    for case_id, kind, query in FUZZY_CASES:
        entry = {"id": case_id, "kind": kind, "query": query}
        try:
            entry["canonical"] = run_fuzzy_case(kind, query)
        except bot.EntityNotFoundError as e:
            entry["error"] = type(e).__name__
            entry["message"] = e.show_message()
        fuzzy_results.append(entry)
        status = "error=" + entry["error"] if "error" in entry else entry["canonical"]
        print(f"{case_id}: {status}")

    fuzzy_out_path = os.path.join(os.path.dirname(__file__), "..", "test", "fixtures", "fuzzy-fixtures.json")
    with open(fuzzy_out_path, "w", encoding="utf-8") as f:
        json.dump(fuzzy_results, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(fuzzy_results)} fuzzy fixtures to {fuzzy_out_path}")

    # Full alias-index dumps (not just spot samples) for the TS port's
    # data/aliasIndex.ts to compare against wholesale, since collision
    # resolution depends on dictionary iteration order and is easy to get
    # subtly wrong for a handful of entries out of ~2000.
    import parse

    alias_dicts = {
        "targets_dictionary": parse.targets_dictionary,
        "weapons_dictionary": parse.weapons_dictionary,
        "all_dictionary": parse.all_dictionary,
        "husk_dictionary": parse.husk_dictionary,
        "vehicle_dictionary": parse.vehicle_dictionary,
    }
    alias_out_path = os.path.join(os.path.dirname(__file__), "..", "test", "fixtures", "alias-index-fixtures.json")
    with open(alias_out_path, "w", encoding="utf-8") as f:
        json.dump(alias_dicts, f, ensure_ascii=False)
    sizes = ", ".join(f"{k}={len(v)}" for k, v in alias_dicts.items())
    print(f"Wrote alias-index fixtures ({sizes}) to {alias_out_path}")

    # Every distinct word that can ever reach utils.singularize() in
    # production (post Locations.csv merge, since that adds town/relic
    # vocabulary too) -> inflect's actual output. inflect's fallback for
    # unrecognized words is more aggressive than most JS pluralize libraries
    # (naively strips trailing "s"), so this is the ground truth the TS port
    # validates its singularize() against, word by word.
    import re

    words = set()
    for d in (parse.targets, parse.weapons):
        for key, value in d.items():
            candidates = [value.get("Name", ""), key]
            if "Additional Names" in value:
                candidates.extend(value["Additional Names"].split(";"))
            for c in candidates:
                c = re.sub(r"[^\w\s]", "", c.lower().strip(), flags=re.UNICODE)
                c = re.sub(r"\s+", " ", c)
                words.update(c.split())

    import inflect

    inflector = inflect.engine()
    singular_map = {}
    for w in sorted(words):
        result = inflector.singular_noun(w)
        singular_map[w] = result if result else w

    singularize_out_path = os.path.join(
        os.path.dirname(__file__), "..", "test", "fixtures", "singularize-fixtures.json"
    )
    with open(singularize_out_path, "w", encoding="utf-8") as f:
        json.dump(singular_map, f, ensure_ascii=False)
    print(f"Wrote {len(singular_map)} singularize fixtures to {singularize_out_path}")

    # Programmatic typo-query -> ground-truth-winner fixtures. fuzzball (the
    # JS fuzzywuzzy port used for the TS matcher) diverges from fuzzywuzzy's
    # raw scores by a few points on ~8% of pairs (rounding/algorithm
    # differences deep in partial_ratio), so the TS port is validated on
    # WHICH canonical name wins, not exact score values - matching the
    # plan's own stated bar for fuzzy-match parity.
    import random

    random.seed(7)

    def make_typo(word, rng):
        chars = list(word)
        if len(chars) < 4:
            return "".join(chars)
        kind = rng.choice(["swap", "drop", "dup"])
        i = rng.randrange(1, len(chars) - 1)
        if kind == "swap":
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
        elif kind == "drop":
            del chars[i]
        else:
            chars.insert(i, chars[i])
        return "".join(chars)

    canonical_targets = sorted({v for v in parse.targets_dictionary.values()})
    canonical_weapons = sorted({v for v in parse.weapons_dictionary.values()})
    sample_targets = random.sample(canonical_targets, 40)
    sample_weapons = random.sample(canonical_weapons, 20)

    winner_results = []
    for name in sample_targets:
        query = make_typo(name.lower(), random)
        try:
            canonical, _ = fuzzy.fuzzy_match_target_name(query)
            winner_results.append({"kind": "target", "query": query, "source_name": name, "canonical": canonical})
        except Exception as e:
            winner_results.append({"kind": "target", "query": query, "source_name": name, "error": type(e).__name__})
    for name in sample_weapons:
        query = make_typo(name.lower(), random)
        try:
            canonical = fuzzy.fuzzy_match_weapon_name(query)
            winner_results.append({"kind": "weapon", "query": query, "source_name": name, "canonical": canonical})
        except Exception as e:
            winner_results.append({"kind": "weapon", "query": query, "source_name": name, "error": type(e).__name__})

    winner_out_path = os.path.join(os.path.dirname(__file__), "..", "test", "fixtures", "fuzzy-winner-fixtures.json")
    with open(winner_out_path, "w", encoding="utf-8") as f:
        json.dump(winner_results, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(winner_results)} fuzzy winner-parity fixtures to {winner_out_path}")

    # Raw score comparison across a broad (query, key) sample - documents the
    # fuzzball/fuzzywuzzy scoring divergence for future reference (e.g. if
    # fuzzball is upgraded and scores drift further from this baseline).
    from fuzzywuzzy import fuzz as fw

    scoring_queries = [
        "silverhnad", "hades net", "boarder base", "alekto cannon", "power plant husk",
        "tremola", "howitzer", "safe hous", "infantry support gun", "watch tower",
        "a3 harpa", "150", "garrison hous", "bt pad", "aegoceru fortres",
    ]
    scoring_target_keys = list(parse.targets_dictionary.keys())
    scoring_weapon_keys = list(parse.weapons_dictionary.keys())
    scoring_pairs = []
    for q in scoring_queries:
        for k in random.sample(scoring_target_keys, 15):
            scoring_pairs.append((q, k))
        for k in random.sample(scoring_weapon_keys, 5):
            scoring_pairs.append((q, k))

    scoring_results = [
        {
            "a": a,
            "b": b,
            "ratio": fw.ratio(a, b),
            "partial_ratio": fw.partial_ratio(a, b),
            "token_sort_ratio": fw.token_sort_ratio(a, b),
            "token_set_ratio": fw.token_set_ratio(a, b),
        }
        for a, b in scoring_pairs
    ]
    scoring_out_path = os.path.join(os.path.dirname(__file__), "..", "test", "fixtures", "fuzzy-scoring-fixtures.json")
    with open(scoring_out_path, "w", encoding="utf-8") as f:
        json.dump(scoring_results, f, ensure_ascii=False)
    print(f"Wrote {len(scoring_results)} fuzzy scoring fixtures to {scoring_out_path}")

    freetext_results = [
        {"message": message, "result": parse_free_text_query(message)} for message in FREETEXT_CASES
    ]
    freetext_out_path = os.path.join(
        os.path.dirname(__file__), "..", "test", "fixtures", "freetext-query-fixtures.json"
    )
    with open(freetext_out_path, "w", encoding="utf-8") as f:
        json.dump(freetext_results, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(freetext_results)} free-text query fixtures to {freetext_out_path}")


if __name__ == "__main__":
    main()
