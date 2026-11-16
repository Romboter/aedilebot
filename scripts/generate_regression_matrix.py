"""Broad Python-vs-TypeScript regression matrix (issue #23).

Runs the live Python calculator over every target x a set of representative
weapons (kill / disable / dehusk), every weapon x a set of representative
targets, every statsheet, and a list of free-text chat queries end to end.
bot-ts/test/regression/matrix.spec.ts replays the same inputs through the TS
port and demands identical output, error type and error message.

    venv/Scripts/python.exe scripts/generate_regression_matrix.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import bot
import calculator
import parse

sys.path.insert(0, os.path.dirname(__file__))
from generate_fixtures import FREETEXT_CASES, parse_free_text_query  # noqa: E402

WEAPONS = ["40mm", "68mm", "150mm", "300mm", "7.62mm", "RPG", "Tremola Grenade GPb-1", "satchel"]
TARGETS = ["40-250 “Alekto” Heavy Cannon", "Border base", "Safe House", "Power Plant Husk", "Infantry Support Gun (ISG)"]
EXTRA_FREETEXT = [
    "how many mammons to kill a ghouse",
    "how many 150mm to kill a facility mine",
    "how much 40mm to destroy a tier 3 ISG",
    "how many sticky bombs to dehusk a refinery husk",
    "how many hydras to disable a harpa",
    "how many 40 mm to kill a bunker base",
]


def record(operation, args):
    entry = {"operation": operation, "input": list(args)}
    try:
        out = {
            "kill": calculator.general_kill_handler,
            "disable": calculator.general_disable_handler,
            "dehusk": calculator.general_dehusk_handler,
            "statsheet": calculator.statsheet_handler,
        }[operation](*args)
        if isinstance(out, bot.EntityNotFoundError):
            entry["error"], entry["message"] = type(out).__name__, out.show_message()
        elif isinstance(out, tuple):
            entry["output"] = list(out)
        else:
            entry["output"] = out
    except Exception as e:  # recorded, not hidden: the TS port must fail the same way
        entry["error"] = type(e).__name__
        entry["message"] = e.show_message() if hasattr(e, "show_message") else str(e)
    return entry


def main():
    cases = []
    targets = sorted(set(parse.targets_dictionary.values()))
    weapons = sorted(set(parse.weapons_dictionary.values()))
    for t in targets:
        for w in WEAPONS:
            for op in ("kill", "disable", "dehusk"):
                cases.append(record(op, (w, t)))
    for w in weapons:
        for t in TARGETS:
            cases.append(record("kill", (w, t)))
    for name in weapons + targets:
        cases.append(record("statsheet", (name,)))

    freetext = []
    for message in FREETEXT_CASES + EXTRA_FREETEXT:
        parsed = parse_free_text_query(message)
        entry = {"message": message, "parsed": parsed}
        if parsed and parsed["operation"] in ("kill", "disable", "dehusk"):
            entry["result"] = record(parsed["operation"], (parsed["weapon"], parsed["target"]))
        freetext.append(entry)

    out = os.path.join(os.path.dirname(__file__), "..", "test", "fixtures", "regression-matrix.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"cases": cases, "freetext": freetext}, f, ensure_ascii=False, separators=(",", ":"))
    errs = sum(1 for c in cases if "error" in c)
    print(f"{len(cases)} cases ({errs} errors), {len(freetext)} free-text -> {out} ({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
