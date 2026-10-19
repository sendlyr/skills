"""Tests for skills/designing-lifecycle-states/scripts/state_audit.py.

End-to-end runs on the Practica example (asserting examples/practica/answer_key.json),
plus small hand-made inputs for ordering, UNOBSERVABLE precedence, unknown fields,
bad rules and the Fisher/Holm pairwise flag.
"""

import csv
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "designing-lifecycle-states" / "scripts" / "state_audit.py"
EXAMPLE = ROOT / "examples" / "practica"
KEY = json.loads((EXAMPLE / "answer_key.json").read_text())["designing-lifecycle-states"]


def run(args, out_dir):
    proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, args), "--out", str(out_dir)],
                          capture_output=True, text=True)
    result = None
    if proc.returncode == 0:
        result = json.loads((Path(out_dir) / "result.json").read_text())
    return proc, result


def ids(result, fid):
    return [f["states"] for f in result["findings"] if f["id"] == fid]


class TestExample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        facts = EXAMPLE / "observational" / "facts.csv"
        t0 = time.perf_counter()
        cls.flawed_proc, cls.flawed = run(
            ["--states", EXAMPLE / KEY["flawed_model"], "--facts", facts, "--outcome", "converted"],
            tmp / "flawed")
        cls.flawed_seconds = time.perf_counter() - t0
        t0 = time.perf_counter()
        cls.good_proc, cls.good = run(
            ["--states", EXAMPLE / KEY["good_model"], "--facts", facts, "--outcome", "converted",
             "--emit-user-file"], tmp / "good")
        cls.good_seconds = time.perf_counter() - t0
        cls.out = tmp

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_runs_fast_and_cleanly(self):
        self.assertEqual(self.flawed_proc.returncode, 0, self.flawed_proc.stderr)
        self.assertEqual(self.good_proc.returncode, 0, self.good_proc.stderr)
        self.assertLess(self.flawed_seconds, 10)
        self.assertLess(self.good_seconds, 10)

    def test_required_keys(self):
        for r in (self.flawed, self.good):
            for key in ("schema_version", "buckets", "pairwise", "findings"):
                self.assertIn(key, r)
            for b in r["buckets"].values():
                for key in ("users", "measured", "outcome_rate", "ci"):
                    self.assertIn(key, b)
            for p in r["pairwise"]:
                for key in ("p", "p_holm", "distinguishable"):
                    self.assertIn(key, p)
            for f in r["findings"]:
                for key in ("id", "states", "message"):
                    self.assertIn(key, f)

    def test_flawed_findings_match_answer_key(self):
        truth = KEY["flawed_findings"]
        unreachable = {s for states in ids(self.flawed, "unreachable_state") for s in states}
        self.assertEqual(unreachable, set(truth["unreachable_states"]))
        self.assertEqual(self.flawed["buckets"]["NEW"]["users"], 0)
        dup = [set(s) for s in ids(self.flawed, "duplicate_ask")]
        for pair in truth["duplicate_asks"]:
            self.assertIn(set(pair), dup)
        sss = {s for states in ids(self.flawed, "success_state_sends") for s in states}
        self.assertEqual(sss, set(truth["success_state_sends"]))
        ind = [set(s) for s in ids(self.flawed, "indistinguishable_pair")]
        for pair in truth["indistinguishable_pairs"]:
            self.assertIn(set(pair), ind)

    def test_unreachable_explains_the_captor(self):
        msg = [f["message"] for f in self.flawed["findings"] if f["id"] == "unreachable_state"][0]
        self.assertIn("NEW never matches", msg)
        self.assertIn("AT_RISK", msg)

    def test_good_model_is_clean(self):
        truth = KEY["good_findings"]
        self.assertEqual({s for x in ids(self.good, "success_state_sends") for s in x},
                         set(truth["success_state_sends"]))
        self.assertEqual({s for x in ids(self.good, "unreachable_state") for s in x},
                         set(truth["unreachable_states"]))
        self.assertEqual(ids(self.good, "duplicate_ask"), truth["duplicate_asks"])
        self.assertEqual(ids(self.good, "indistinguishable_pair"), [])

    def test_good_model_has_unobservable_rows(self):
        self.assertTrue(KEY["unobservable_expected"])
        self.assertGreater(self.good["buckets"]["UNOBSERVABLE"]["users"], 0)
        self.assertTrue(ids(self.good, "unobservable_rows"))

    def test_every_user_bucketed_once(self):
        total = sum(b["users"] for b in self.good["buckets"].values())
        self.assertEqual(total, self.good["inputs"]["users"])
        with (self.out / "good" / "users.csv").open() as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), total)
        self.assertEqual(len({r["user_id"] for r in rows}), total)

    def test_reports_never_contain_user_ids(self):
        for name in ("flawed", "good"):
            for f in ("report.md", "result.json"):
                text = (self.out / name / f).read_text()
                self.assertIsNone(re.search(r"usr_\d+", text), f"{name}/{f} leaks a user id")

    def test_report_sections_in_order(self):
        text = (self.out / "flawed" / "report.md").read_text()
        heads = ["## 1. The model", "## 2. Where users land", "## 3. Findings",
                 "## 4. Does each distinction", "## 5. Budget exposure"]
        positions = [text.index(h) for h in heads]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(text.count("*What to fix:*"), len(self.flawed["findings"]))


class TestSmallInputs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def files(self, toml_text, header, rows):
        states = self.dir / "states.toml"
        states.write_text(toml_text)
        facts = self.dir / "facts.csv"
        with facts.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        return states, facts

    def audit(self, toml_text, header, rows, *extra):
        states, facts = self.files(toml_text, header, rows)
        return run(["--states", states, "--facts", facts, "--outcome", "y", "--emit-user-file", *extra],
                   self.dir / "out")

    def buckets_by_user(self):
        with (self.dir / "out" / "users.csv").open() as fh:
            return {r["user_id"]: (r["bucket"], r["reason"]) for r in csv.DictReader(fh)}

    BASE = """
[model]
name = "t"
email_actor = "learner"
[unobservable]
required_fields = ["x"]
[[exclusions]]
name = "EXCLUDED"
when = "is_test == 1"
reason = "test_account"
[[states]]
name = "DONE"
when = "x >= 2"
success = true
send = false
[[states]]
name = "SOME"
when = "x >= 1"
send = true
ask = "Do one more"
actor = "learner"
[[states]]
name = "NONE"
when = "x == 0"
send = true
ask = "Do the first one"
actor = "learner"
[fallback]
name = "UNCLASSIFIED"
"""

    def test_first_match_wins_and_unobservable_first(self):
        rows = [["u1", "3", "0", "1"],     # fits DONE and SOME: DONE wins (first match)
                ["u2", "1", "0", "0"],     # SOME
                ["u3", "", "1", "1"],      # blank required field AND test account: UNOBSERVABLE wins
                ["u4", "0", "1", ""],      # test account: EXCLUDED before NONE
                ["u5", "-1", "0", "0"]]    # nothing fits: fallback
        proc, r = self.audit(self.BASE, ["user_id", "x", "is_test", "y"], rows)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        got = self.buckets_by_user()
        self.assertEqual(got["u1"], ("DONE", "DONE"))
        self.assertEqual(got["u2"], ("SOME", "SOME"))
        self.assertEqual(got["u3"], ("UNOBSERVABLE", "missing:x"))
        self.assertEqual(got["u4"], ("EXCLUDED", "test_account"))
        self.assertEqual(got["u5"], ("UNCLASSIFIED", "no_state_matched"))
        self.assertEqual(r["buckets"]["EXCLUDED"]["measured"], 0)      # blank outcome is unmeasured
        self.assertEqual(r["buckets"]["EXCLUDED"]["users"], 1)
        self.assertIsNone(r["buckets"]["EXCLUDED"]["outcome_rate"])
        self.assertTrue(ids(r, "unobservable_rows"))
        self.assertTrue(ids(r, "small_state"))

    def test_unknown_field_is_null_and_flagged(self):
        toml_text = self.BASE.replace('when = "x == 0"', 'when = "x == 0 or typo_field >= 1"')
        toml_text = toml_text.replace('when = "x >= 1"', 'when = "goal == 1"')
        rows = [["u1", "0", "0", "1"], ["u2", "1", "0", "0"]]
        proc, r = self.audit(toml_text, ["user_id", "x", "is_test", "y"], rows)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        unknown = {f["field"] for f in r["findings"] if f["id"] == "unknown_field"}
        self.assertEqual(unknown, {"typo_field", "goal"})
        # SOME reads only the missing column, so it can never match.
        msg = [f["message"] for f in r["findings"] if f["id"] == "unreachable_state" and f["states"] == ["SOME"]]
        self.assertTrue(msg and "not a column" in msg[0], msg)
        self.assertEqual(self.buckets_by_user()["u2"][0], "UNCLASSIFIED")

    def test_unreachable_names_the_earlier_state(self):
        toml_text = self.BASE.replace('name = "NONE"\nwhen = "x == 0"', 'name = "NONE"\nwhen = "x >= 5"')
        rows = [["u1", "6", "0", "1"], ["u2", "1", "0", "0"]]
        proc, r = self.audit(toml_text, ["user_id", "x", "is_test", "y"], rows)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        f = [f for f in r["findings"] if f["id"] == "unreachable_state" and f["states"] == ["NONE"]][0]
        self.assertEqual(f["captured_by"], {"DONE": 1})
        self.assertIn("captured by DONE", f["message"])

    def test_model_checks(self):
        toml_text = """
[model]
name = "t"
email_actor = "parent"
[[states]]
name = "A"
when = "x >= 2"
send = true
ask = "Keep your streak going!"
actor = "parent"
[[states]]
name = "B"
when = "x >= 1"
send = true
ask = "keep your   streak going"
actor = "child"
[[states]]
name = "C"
when = "x == 0"
send = true
"""
        rows = [["u1", "2", "1"], ["u2", "1", "0"], ["u3", "0", "0"]]
        proc, r = self.audit(toml_text, ["user_id", "x", "y"], rows)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(["A", "B"], ids(r, "duplicate_ask"))
        self.assertIn(["B"], ids(r, "actor_mismatch"))
        self.assertIn(["C"], ids(r, "actor_mismatch"))          # sends without a declared actor
        self.assertIn(["C"], ids(r, "sending_state_without_ask"))
        self.assertEqual(ids(r, "no_success_state"), [[]])
        self.assertNotIn(["A"], ids(r, "actor_mismatch"))

    def test_success_state_that_sends(self):
        toml_text = self.BASE.replace("success = true\nsend = false", 'success = true\nsend = true\nask = "Celebrate"\nactor = "learner"')
        proc, r = self.audit(toml_text, ["user_id", "x", "is_test", "y"], [["u1", "2", "0", "1"]])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(ids(r, "success_state_sends"), [["DONE"]])
        self.assertEqual(r["budget_exposure"]["sending_and_success_users"], 1)

    def test_fisher_holm_flags_only_the_close_pair(self):
        toml_text = """
[model]
name = "t"
email_actor = "learner"
[[states]]
name = "HIGH"
when = "g == 2"
success = true
send = false
[[states]]
name = "HIGH_TOO"
when = "g == 1"
send = true
ask = "Ask one"
actor = "learner"
[[states]]
name = "LOW"
when = "g == 0"
send = true
ask = "Ask two"
actor = "learner"
"""
        rows = []
        for g, n, k in ((2, 40, 20), (1, 40, 21), (0, 40, 2)):     # 50% vs 52.5% vs 5%
            rows += [[f"g{g}_{i}", str(g), "1" if i < k else "0"] for i in range(n)]
        proc, r = self.audit(toml_text, ["user_id", "g", "y"], rows)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(r["pairwise"]), 3)
        by_pair = {frozenset(p["states"]): p for p in r["pairwise"]}
        close = by_pair[frozenset({"HIGH", "HIGH_TOO"})]
        self.assertFalse(close["distinguishable"])
        self.assertGreaterEqual(close["p_holm"], close["p"])
        self.assertTrue(by_pair[frozenset({"HIGH", "LOW"})]["distinguishable"])
        self.assertTrue(by_pair[frozenset({"HIGH_TOO", "LOW"})]["distinguishable"])
        self.assertEqual([set(s) for s in ids(r, "indistinguishable_pair")], [{"HIGH", "HIGH_TOO"}])
        # Raising --min-users above the measured count leaves every pair untested.
        proc, r = self.audit(toml_text, ["user_id", "g", "y"], rows, "--min-users", "41")
        self.assertEqual(r["pairwise"], [])
        self.assertEqual(ids(r, "indistinguishable_pair"), [])

    def test_bad_rule_exits_2_naming_state_and_rule(self):
        toml_text = self.BASE.replace('when = "x >= 1"', 'when = "x >= "')
        proc, _ = self.audit(toml_text, ["user_id", "x", "is_test", "y"], [["u1", "1", "0", "1"]])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("SOME", proc.stderr)
        self.assertIn("x >= ", proc.stderr)
        self.assertIn("states.toml", proc.stderr)

    def test_missing_outcome_column_exits_2(self):
        proc, _ = self.audit(self.BASE, ["user_id", "x", "is_test"], [["u1", "1", "0"]])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("facts.csv", proc.stderr)
        self.assertIn("y", proc.stderr)

    def test_bad_outcome_value_exits_2_with_row(self):
        proc, _ = self.audit(self.BASE, ["user_id", "x", "is_test", "y"],
                             [["u1", "1", "0", "1"], ["u2", "1", "0", "maybe"]])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("facts.csv:3", proc.stderr)

    def test_help_explains_every_flag(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        for flag in ("--states", "--facts", "--outcome", "--min-users", "--emit-user-file", "--out"):
            self.assertIn(flag, proc.stdout)


if __name__ == "__main__":
    unittest.main()
