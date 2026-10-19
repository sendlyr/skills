"""Tests for skills/finding-leading-indicators/scripts/score_signals.py.

Run: python3 -m unittest tests/test_score_signals.py -v
"""

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "finding-leading-indicators" / "scripts" / "score_signals.py"
PRACTICA = ROOT / "examples" / "practica"
ACCOUNTS = PRACTICA / "observational" / "accounts.csv"
EVENTS = PRACTICA / "observational" / "events.csv"
ANSWER_KEY = json.loads((PRACTICA / "answer_key.json").read_text(encoding="utf-8"))
KEY = ANSWER_KEY["finding-leading-indicators"]


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def event_of(key):
    return key.split("@", 1)[0]


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


class TestPracticaEndToEnd(unittest.TestCase):
    """The planted truths in examples/practica/answer_key.json."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="score_signals_"))
        base = ["--accounts", ACCOUNTS, "--events", EVENTS,
                "--outcome-window-days", KEY["args"]["outcome_window_days"],
                "--decision-window-days", KEY["args"]["decision_window_days"],
                "--email-actor", KEY["args"]["email_actor"]]
        start = time.perf_counter()
        cls.proc = run(*base, "--out", cls.tmp / "main")
        cls.seconds = time.perf_counter() - start
        cls.proc14 = run(*base, "--windows", f"1,3,{KEY['windows_beyond_decision_window_refused']}",
                         "--out", cls.tmp / "w14")
        cls.result = json.loads((cls.tmp / "main" / "result.json").read_text(encoding="utf-8"))
        cls.report = (cls.tmp / "main" / "report.md").read_text(encoding="utf-8")
        cls.by_key = {c["key"]: c for c in cls.result["candidates"]}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_runs_fast_and_cleanly(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertLess(self.seconds, 10.0)
        self.assertIn("## Summary", self.proc.stdout)          # report echoed to stdout

    def test_required_keys(self):
        for k in ("schema_version", "inputs", "candidates", "ranked", "recommendation",
                  "nothing_vs_something", "refused"):
            self.assertIn(k, self.result)
        for k in ("accounts", "mature", "immature", "excluded_outcome_in_window"):
            self.assertIn(k, self.result["inputs"])
        for k in ("primary", "supporting", "caveats"):
            self.assertIn(k, self.result["recommendation"])
        for c in self.result["candidates"]:
            for k in ("event", "threshold", "window_days", "actor", "population", "hits", "coverage",
                      "hit_rate", "miss_rate", "lift", "lift_ci", "relative_lift", "rank_score",
                      "readiness", "flags", "holdout"):
                self.assertIn(k, c)

    def test_primary_is_goal_set(self):
        primary = self.result["recommendation"]["primary"]
        self.assertIsNotNone(primary)
        self.assertEqual(primary["event"], KEY["top_event"])
        self.assertEqual(primary["threshold"], KEY["top_threshold"])
        self.assertLessEqual(primary["window_days"], KEY["top_window_days_max"])
        cand = self.by_key[primary["key"]]
        self.assertEqual(cand["readiness"], "ready")
        self.assertTrue(cand["holdout"]["replicated"])

    def test_supporting_is_lesson_completed(self):
        supporting = self.result["recommendation"]["supporting"]
        self.assertIsNotNone(supporting)
        self.assertEqual(supporting["event"], KEY["supporting_event"])

    def test_decoys_not_in_top3(self):
        top3 = [event_of(k) for k in self.result["ranked"][:3]]
        for bad in KEY["must_not_rank_top3"]:
            self.assertNotIn(bad, top3)

    def test_too_broad(self):
        tb = KEY["too_broad"]
        key = f"{tb['event']}@>={tb['threshold']}/{tb['window_days']}d"
        self.assertIn("too_broad", self.by_key[key]["flags"])
        self.assertNotIn(key, self.result["ranked"])

    def test_not_actionable_actor(self):
        name = KEY["not_actionable_actor"]
        cands = [c for c in self.result["candidates"] if c["event"] == name]
        self.assertTrue(cands)
        for c in cands:
            self.assertIn("not_actionable_actor", c["flags"])
            self.assertNotIn(c["key"], self.result["ranked"])

    def test_immature_counts(self):
        inputs = self.result["inputs"]
        counts = ANSWER_KEY["observational_counts"]
        self.assertGreater(inputs["immature"], 0)
        self.assertEqual(inputs["accounts"], counts["accounts"])
        self.assertEqual(inputs["mature"], counts["mature_accounts"])
        self.assertEqual(inputs["immature"], counts["immature_accounts"])

    def test_window_beyond_decision_refused(self):
        self.assertEqual(self.proc14.returncode, 0, self.proc14.stderr)
        result = json.loads((self.tmp / "w14" / "result.json").read_text(encoding="utf-8"))
        w = KEY["windows_beyond_decision_window_refused"]
        refused = [r for r in result["refused"] if r.get("window_days") == w]
        self.assertEqual(len(refused), 1)
        self.assertEqual(refused[0]["reason"], "window_beyond_decision")
        self.assertFalse([c for c in result["candidates"] if c["window_days"] == w])

    def test_nothing_vs_something(self):
        nvs = KEY["nothing_vs_something"]
        item = next(x for x in self.result["nothing_vs_something"] if x["event"] == nvs["event"])
        rate = {b["bucket"]: b["rate"] for b in item["buckets"]}
        self.assertLess(rate["0"], rate["1"] - 0.20)            # 0 is far below 1
        self.assertLess(abs(rate["1"] - rate["3-4"]), 0.10)      # 1 vs 3-4 within 10pp
        self.assertIsNotNone(item["reading"]["share_of_separation_at_1"])

    def test_report_sections_and_no_ids(self):
        for heading in ("## Summary", "## Data", "## Top candidates", "## Nothing vs something",
                        "## Refused and flagged", "## Caveats"):
            self.assertIn(heading, self.report)
        self.assertIn("predictive, not causal", self.report.lower())
        with open(ACCOUNTS, newline="", encoding="utf-8") as fh:
            ids = [row["account_id"] for row in csv.DictReader(fh)]
        self.assertFalse([i for i in ids if i in self.report])
        self.assertNotIn("acc_", self.report)


class TestSmallInputs(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="score_signals_unit_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, accounts, events, *extra, ow=7, dw=3):
        a, e = self.tmp / "accounts.csv", self.tmp / "events.csv"
        write_csv(a, *accounts)
        write_csv(e, *events)
        out = self.tmp / "out"
        proc = run("--accounts", a, "--events", e, "--outcome-window-days", ow,
                   "--decision-window-days", dw, "--out", out, *extra)
        result = report = None
        if proc.returncode == 0:
            result = json.loads((out / "result.json").read_text(encoding="utf-8"))
            report = (out / "report.md").read_text(encoding="utf-8")
        return proc, result, report

    @staticmethod
    def leakage_world():
        """20 accounts, anchors 1..20 Jan 2026. Days 1-10 are discovery and 11-20 holdout
        (holdout share 0.5); both halves repeat the same 10-account pattern."""
        # (outcome offset hours or None, event offset hours or None)
        pattern = [
            (12, 1),        # outcome inside the 1-day window -> dropped for W=1 and W=3
            (48, 30),       # outcome inside the 3-day window -> dropped for W=3; event after day 1
            (120, 2),       # hit in both windows, converted
            (120, 24),      # event exactly at anchor+1d: not in [anchor, anchor+1d)
            (None, -1),     # event before the anchor: never counted; blank outcome
            (None, 3),      # hit, blank outcome = not converted
            (240, 3),       # outcome after the 7-day window = not converted
            (None, None),
            (None, None),
            (144, None),    # converted with no event
        ]
        accounts, events = [], []
        for i in range(20):
            day = i + 1
            aid = f"u{day:02d}"
            out_h, ev_h = pattern[i % 10]
            accounts.append([aid, _iso(day, 0), "" if out_h is None else _iso(day, out_h), "2026-03-01"])
            if ev_h is not None:
                events.append([aid, "x", _iso(day, ev_h), "learner"])
        return (["account_id", "anchor_at", "outcome_at", "observed_until"], accounts), \
               (["account_id", "event_name", "occurred_at", "actor"], events)

    def test_leakage_guard(self):
        accounts, events = self.leakage_world()
        proc, result, _ = self.run_tool(accounts, events, "--windows", "1,3", "--thresholds", "1",
                                        "--min-users", "1", "--holdout-share", "0.5")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        inputs = result["inputs"]
        self.assertEqual(inputs["mature"], 20)
        self.assertEqual(inputs["discovery"], 10)
        self.assertEqual(inputs["excluded_outcome_in_window"], {"1": 2, "3": 4})
        self.assertEqual(inputs["outcome_after_window"], 2)
        self.assertEqual(inputs["event_rows_before_anchor"], 2)
        by_key = {c["key"]: c for c in result["candidates"]}
        w1, w3 = by_key["x@>=1/1d"], by_key["x@>=1/3d"]
        self.assertEqual(w1["population"], 9)       # 10 discovery minus 1 outcome-in-window
        self.assertEqual(w3["population"], 8)       # minus 2
        self.assertEqual(w1["hits"], 3)             # boundary, late and pre-anchor events not counted
        self.assertEqual(w3["hits"], 4)
        self.assertEqual(w1["positives"], 4)        # rows 2, 3, 4 and 10 converted; row 7 is too late
        self.assertEqual(w3["positives"], 3)        # row 2 is dropped by the leakage guard

    def test_immature_excluded(self):
        header = ["account_id", "anchor_at", "outcome_at", "observed_until"]
        rows = [
            ["a1", "2026-01-01", "", "2026-02-01"],          # mature
            ["a2", "2026-01-02", "", "2026-01-05"],          # observed only 3 days -> immature
            ["a3", "2026-01-10", "", ""],                    # blank observed_until -> as_of; mature
            ["a4", "2026-01-18", "", ""],                    # 2 days before as_of -> immature
            ["a5", "2026-01-15", "", "2026-02-01"],          # as_of caps observed_until -> immature
            ["a6", "2026-01-25", "", ""],                    # starts after as_of -> immature
        ]
        events = (["account_id", "event_name", "occurred_at"], [["a1", "x", "2026-01-01T05:00:00"]])
        proc, result, report = self.run_tool((header, rows), events, "--as-of", "2026-01-20",
                                             "--min-users", "1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        inputs = result["inputs"]
        self.assertEqual(inputs["accounts"], 6)
        self.assertEqual(inputs["mature"], 2)
        self.assertEqual(inputs["immature"], 4)
        self.assertEqual(inputs["immature_started_after_as_of"], 1)
        self.assertEqual(inputs["observed_until_blank"], 3)
        self.assertIn("Immature (too new, left out): 4", report)

    def test_blank_outcome_is_counted_and_not_converted(self):
        header = ["account_id", "anchor_at", "outcome_at", "observed_until"]
        rows = [[f"b{i}", "2026-01-01", ("2026-01-05" if i < 3 else ""), "2026-02-01"] for i in range(10)]
        events = (["account_id", "event_name", "occurred_at"],
                  [[f"b{i}", "x", "2026-01-01T06:00:00Z"] for i in range(5)])
        proc, result, report = self.run_tool((header, rows), events, "--min-users", "1",
                                             "--windows", "1", "--thresholds", "1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result["inputs"]["outcome_blank"], 7)
        self.assertEqual(result["inputs"]["positives"], 3)
        self.assertIn("blank outcome_at", report)

    def test_missing_outcome_column_still_runs(self):
        accounts = (["account_id", "anchor_at"], [["c1", "2026-01-01"], ["c2", "2026-01-02"]])
        events = (["account_id", "event_name", "occurred_at"], [["c1", "x", "2026-01-01T01:00:00Z"]])
        proc, result, _ = self.run_tool(accounts, events, "--min-users", "1", "--as-of", "2026-03-01")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(result["inputs"]["has_outcome_column"])
        self.assertEqual(result["inputs"]["outcome_blank"], 2)
        self.assertIsNone(result["recommendation"]["primary"])

    def test_malformed_timestamp_exit_2(self):
        accounts = (["account_id", "anchor_at"], [["m1", "2026-01-01"], ["m2", "2026-01-02"]])
        events = (["account_id", "event_name", "occurred_at"],
                  [["m1", "x", "2026-01-01T01:00:00Z"], ["m2", "x", "not-a-date"]])
        proc, _, _ = self.run_tool(accounts, events)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("events.csv:3", proc.stderr)
        self.assertIn("occurred_at", proc.stderr)
        self.assertNotIn("m2", proc.stderr)                    # no IDs in messages

        bad_accounts = (["account_id", "anchor_at"], [["m1", "2026-01-01"], ["m2", "2026-13-45"]])
        proc, _, _ = self.run_tool(bad_accounts, events)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("accounts.csv:3", proc.stderr)
        self.assertIn("anchor_at", proc.stderr)

    def test_missing_column_exit_2(self):
        accounts = (["account_id", "signup"], [["m1", "2026-01-01"]])
        events = (["account_id", "event_name", "occurred_at"], [["m1", "x", "2026-01-01T01:00:00Z"]])
        proc, _, _ = self.run_tool(accounts, events)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("accounts.csv", proc.stderr)
        self.assertIn("anchor_at", proc.stderr)
        self.assertIn("missing required column", proc.stderr)

        ok_accounts = (["account_id", "anchor_at"], [["m1", "2026-01-01"]])
        no_time = (["account_id", "event_name"], [["m1", "x"]])
        proc, _, _ = self.run_tool(ok_accounts, no_time)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("occurred_at", proc.stderr)

    def test_decision_longer_than_outcome_exit_2(self):
        accounts = (["account_id", "anchor_at"], [["m1", "2026-01-01"]])
        events = (["account_id", "event_name", "occurred_at"], [["m1", "x", "2026-01-01T01:00:00Z"]])
        proc, _, _ = self.run_tool(accounts, events, ow=7, dw=10)
        self.assertEqual(proc.returncode, 2)

    def test_actor_flag_and_refused_window(self):
        accounts, events = self.leakage_world()
        header, rows = events
        rows = rows + [[r[0], "nudge", r[2], "system"] for r in rows]
        proc, result, report = self.run_tool(accounts, (header, rows), "--windows", "1,3,7",
                                             "--min-users", "1", "--email-actor", "learner",
                                             "--holdout-share", "0.5")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        nudges = [c for c in result["candidates"] if c["event"] == "nudge"]
        self.assertTrue(nudges)
        for c in nudges:
            self.assertEqual(c["actor"], "system")
            self.assertIn("not_actionable_actor", c["flags"])
            self.assertNotIn(c["key"], result["ranked"])
        self.assertEqual([r["window_days"] for r in result["refused"] if r["kind"] == "window"], [7])
        self.assertNotIn("u0", report)                          # no account IDs in the report


def _iso(day, hours):
    """Timestamp `hours` after midnight UTC on 2026-01-<day> (hours may be negative)."""
    from datetime import datetime, timedelta, timezone
    t = datetime(2026, 1, day, tzinfo=timezone.utc) + timedelta(hours=hours)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    unittest.main()
