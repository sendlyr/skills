#!/usr/bin/env python3
"""Copy the canonical shared blocks in scripts/shared/ into every skill script.

Each skill script that needs a block contains a BEGIN/END marker pair, e.g.

    # --- BEGIN shared:stats (generated from scripts/shared/stats.py; do not edit here) ---
    ...
    # --- END shared:stats ---

This tool replaces whatever is between those markers with the canonical text.
Run with --check to report drift without writing (used by CI).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "scripts" / "shared"
BLOCK_RE = re.compile(
    r"(?P<begin># --- BEGIN shared:(?P<name>[a-z]+) [^\n]*---\n)(?P<body>.*?)(?P<end># --- END shared:(?P=name) ---)",
    re.S,
)


def canonical_blocks() -> dict[str, str]:
    blocks = {}
    for path in sorted(SHARED.glob("*.py")):
        m = BLOCK_RE.search(path.read_text(encoding="utf-8"))
        if m:
            blocks[m.group("name")] = m.group(0)
    return blocks


def skill_scripts() -> list[Path]:
    return sorted(ROOT.glob("skills/*/scripts/*.py"))


def sync(check: bool) -> int:
    blocks = canonical_blocks()
    drift = []
    for path in skill_scripts():
        text = path.read_text(encoding="utf-8")

        def replace(m: re.Match) -> str:
            name = m.group("name")
            if name not in blocks:
                raise SystemExit(f"{path}: unknown shared block {name!r}")
            return blocks[name]

        new = BLOCK_RE.sub(replace, text)
        if new != text:
            drift.append(path.relative_to(ROOT))
            if not check:
                path.write_text(new, encoding="utf-8")
    if drift:
        verb = "out of date" if check else "updated"
        print(f"{len(drift)} script(s) {verb}:\n  " + "\n  ".join(map(str, drift)))
        return 1 if check else 0
    print("All shared blocks are in sync.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report drift; do not write")
    sys.exit(sync(ap.parse_args().check))
