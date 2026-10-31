#!/usr/bin/env python3
"""Validate Markdown links and basic runbook framing without external packages.

Run from anywhere: python3 docs/check_docs.py
Checks only repository-relative links; HTTP(S) destinations are intentionally
not fetched, as network failures do not indicate a broken local document.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LINK = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")
SKIP_PREFIXES = ("http:", "https:", "mailto:", "#", "data:")
INDEX = DOCS / "README.md"


def main() -> int:
    errors: list[str] = []
    files = sorted(DOCS.rglob("*.md"))
    if not INDEX.exists():
        errors.append("docs/README.md is missing")
    if len(files) < 10:
        errors.append(f"Only {len(files)} Markdown docs found; expected handbook plus runbooks")

    for file in files:
        content = file.read_text(encoding="utf-8")
        if not content.startswith("# "):
            errors.append(f"{file.relative_to(ROOT)}: missing H1 title")
        if file.parent.name == "runbooks":
            if "Status" not in content[:1200]:
                errors.append(f"{file.relative_to(ROOT)}: missing status/scope in opening")
            if not any(word in content.lower() for word in ("verify", "success criteria", "verification", "validation")):
                errors.append(f"{file.relative_to(ROOT)}: missing verification or success check")

        for match in LINK.finditer(content):
            raw = match.group(1).strip().strip("<>").split(" ", 1)[0]
            if not raw or raw.startswith(SKIP_PREFIXES):
                continue
            path_part = urlsplit(raw).path
            if not path_part:
                continue
            destination = (file.parent / unquote(path_part)).resolve()
            try:
                destination.relative_to(ROOT)
            except ValueError:
                errors.append(f"{file.relative_to(ROOT)}: link escapes repo root: {raw}")
                continue
            if not destination.exists():
                errors.append(f"{file.relative_to(ROOT)}: broken link: {raw}")

    if INDEX.exists():
        index = INDEX.read_text(encoding="utf-8")
        for runbook in sorted((DOCS / "runbooks").glob("*.md")):
            if runbook.name not in index:
                errors.append(f"docs/README.md does not link {runbook.name}")

    if errors:
        for err in errors:
            print("ERROR:", err, file=sys.stderr)
        return 1
    print(f"PASS: {len(files)} Markdown docs checked; relative links and runbook index valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
