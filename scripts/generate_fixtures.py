"""Generates golden regression fixtures by running the current Python calculator
against a curated list of cases. Output feeds the TypeScript rewrite's parity
tests (test/fixtures/calculator-fixtures.json) so behavior can be verified
identical before/after the port. Run from the repo root:

    venv/Scripts/python.exe scripts/generate_fixtures.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import bot
import calculator
import fuzzy
import parse

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


def main():
    results = []
    for case_id, operation, args in CASES:
        entry = {"id": case_id, "operation": operation, "input": args}
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


if __name__ == "__main__":
    main()
