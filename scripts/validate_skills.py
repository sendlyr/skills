#!/usr/bin/env python3
"""Validate every skill folder against the Agent Skills spec and this repo's rules.

Checks per skills/<name>/:
- SKILL.md exists, starts with YAML frontmatter, name matches the folder and the spec
  (1-64 chars, lowercase letters/digits/hyphens, no leading/trailing/double hyphen)
- description present, <= 1024 chars; license is MIT; metadata.version present
- SKILL.md body <= 500 lines
- every relative path mentioned as scripts/..., references/... or assets/... exists
- evals/evals.json is valid and well-formed (skill-creator format)
- each script in scripts/ has a --help that exits 0
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PATH_RE = re.compile(r"(?<![\w/.])((?:scripts|references|assets)/[A-Za-z0-9_.\-/]+\.[a-z]+)")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with '---' frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("frontmatter is not closed with '---'")
    block, body = text[4:end], text[end + 5:]
    data: dict = {}
    current = None
    for raw in block.splitlines():
        if not raw.strip():
            continue
        if raw.startswith("  ") and current is not None:
            k, _, v = raw.strip().partition(":")
            data[current][k.strip()] = v.strip().strip('"')
            continue
        k, _, v = raw.partition(":")
        k, v = k.strip(), v.strip()
        if v == "":
            data[k] = {}
            current = k
        else:
            data[k] = v.strip('"')
            current = None
    return data, body


def check_skill(folder: Path) -> list[str]:
    errs: list[str] = []
    skill_md = folder / "SKILL.md"
    if not skill_md.exists():
        return [f"{folder.name}: missing SKILL.md"]
    text = skill_md.read_text(encoding="utf-8")
    try:
        fm, body = parse_frontmatter(text)
    except ValueError as exc:
        return [f"{folder.name}: {exc}"]
    name = fm.get("name", "")
    if name != folder.name:
        errs.append(f"{folder.name}: frontmatter name {name!r} must match the folder name")
    if not NAME_RE.match(name) or len(name) > 64:
        errs.append(f"{folder.name}: invalid name {name!r}")
    desc = fm.get("description", "")
    if not desc:
        errs.append(f"{folder.name}: description is required")
    elif len(desc) > 1024:
        errs.append(f"{folder.name}: description is {len(desc)} chars (max 1024)")
    if fm.get("license") != "MIT":
        errs.append(f"{folder.name}: license must be MIT")
    if not isinstance(fm.get("metadata"), dict) or not fm["metadata"].get("version"):
        errs.append(f"{folder.name}: metadata.version is required")
    lines = body.count("\n") + 1
    if lines > 500:
        errs.append(f"{folder.name}: SKILL.md body is {lines} lines (max 500)")

    for ref in sorted(set(PATH_RE.findall(text))):
        if not (folder / ref).exists():
            errs.append(f"{folder.name}: SKILL.md mentions {ref}, which does not exist")

    evals = folder / "evals" / "evals.json"
    if not evals.exists():
        errs.append(f"{folder.name}: missing evals/evals.json")
    else:
        try:
            data = json.loads(evals.read_text(encoding="utf-8"))
            if data.get("skill_name") != folder.name:
                errs.append(f"{folder.name}: evals.json skill_name must be {folder.name!r}")
            cases = data.get("evals") or []
            if len(cases) < 3:
                errs.append(f"{folder.name}: evals.json needs at least 3 cases")
            for case in cases:
                for key in ("id", "prompt", "expected_output", "assertions"):
                    if key not in case:
                        errs.append(f"{folder.name}: eval {case.get('id')} is missing {key!r}")
                for f in case.get("files", []):
                    if not (ROOT / f).exists():
                        errs.append(f"{folder.name}: eval {case.get('id')} file {f} does not exist")
        except json.JSONDecodeError as exc:
            errs.append(f"{folder.name}: evals.json is not valid JSON: {exc}")

    for script in sorted((folder / "scripts").glob("*.py")):
        r = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            errs.append(f"{folder.name}: {script.name} --help exited {r.returncode}: {r.stderr.strip()[:200]}")
    return errs


def main() -> int:
    folders = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())
    errors = [e for f in folders for e in check_skill(f)]
    if errors:
        print(f"{len(errors)} problem(s):\n  " + "\n  ".join(errors))
        return 1
    print(f"OK: {len(folders)} skills valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
