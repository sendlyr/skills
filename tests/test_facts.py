"""Tests for facts.json: the public facts other sites copy must match the repo.

Run: python3 -m unittest tests/test_facts.py -v
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS = json.loads((ROOT / "facts.json").read_text(encoding="utf-8"))
PLUGIN = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
README = (ROOT / "README.md").read_text(encoding="utf-8")

NETWORK_MODULES = {
    "socket", "ssl", "http", "urllib", "ftplib", "smtplib", "poplib", "imaplib",
    "nntplib", "telnetlib", "xmlrpc", "socketserver", "asyncio", "selectors", "webbrowser",
}
CREDENTIAL_FLAG = re.compile(r"--(api[-_]?key|access[-_]?key|token|password|secret|credentials?)\b", re.IGNORECASE)


def skill_scripts():
    return sorted((ROOT / "skills").glob("*/scripts/*.py"))


def imported_modules(path):
    mods = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    return mods


class TestFacts(unittest.TestCase):
    def test_matches_plugin_manifest(self):
        for key in ("name", "version", "license", "repository", "homepage"):
            self.assertEqual(FACTS[key], PLUGIN[key], key)

    def test_skills_and_scripts_match_repo(self):
        folders = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir())
        self.assertEqual([s["name"] for s in FACTS["skills"]], folders)
        for skill in FACTS["skills"]:
            scripts = sorted(p.name for p in (ROOT / "skills" / skill["name"] / "scripts").glob("*.py"))
            self.assertEqual(scripts, [skill["script"]], skill["name"])
        self.assertEqual(FACTS["counts"]["skills"], len(folders))
        self.assertEqual(FACTS["counts"]["scripts"], len(skill_scripts()))

    def test_test_count_matches_suite(self):
        suite = unittest.TestLoader().discover(str(ROOT / "tests"), top_level_dir=str(ROOT / "tests"))
        self.assertEqual(FACTS["counts"]["tests"], suite.countTestCases(),
                         "update counts.tests in facts.json")

    def test_install_commands_and_runtime_appear_in_readme(self):
        for cmd in FACTS["install"]["claude_code"] + [FACTS["install"]["agent_skills_cli"]]:
            self.assertIn(cmd, README)
        self.assertIn(f"Python {FACTS['runtime']['python']}", README)

    def test_scripts_are_stdlib_only_offline_and_take_no_credentials(self):
        self.assertEqual(FACTS["runtime"]["third_party_packages"], 0)
        self.assertFalse(FACTS["network"]["scripts_open_network_connections"])
        self.assertFalse(FACTS["network"]["scripts_take_credentials"])
        for script in skill_scripts():
            mods = imported_modules(script)
            rel = script.relative_to(ROOT)
            self.assertEqual(sorted(m for m in mods if m not in sys.stdlib_module_names), [], rel)
            self.assertEqual(sorted(mods & NETWORK_MODULES), [], rel)
            self.assertIsNone(CREDENTIAL_FLAG.search(script.read_text(encoding="utf-8")), rel)

    def test_ci_python_versions_match_workflow(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        match = re.search(r"python:\s*\[([^\]]*)\]", workflow)
        self.assertIsNotNone(match)
        versions = [v.strip().strip("\"'") for v in match.group(1).split(",")]
        self.assertEqual(FACTS["ci"]["python_versions"], versions)


if __name__ == "__main__":
    unittest.main()
