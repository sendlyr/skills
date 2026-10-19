"""Tests for skills/designing-state-journeys/scripts/audit_sends.py.

End-to-end runs on the Practica good and broken experiments (asserting
examples/practica/answer_key.json), plus small hand-made inputs for the SLA arithmetic,
not_needed reach, spacing and cap edges, control contact, termination precedence and
malformed input.
"""

import csv
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "designing-state-journeys" / "scripts" / "audit_sends.py"
EXAMPLE = ROOT / "examples" / "practica"
KEY = json.loads((EXAMPLE / "answer_key.json").read_text())["designing-state-journeys"]
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def iso(hours):
    return (T0 + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(args, out_dir):
    proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, args), "--out", str(out_dir)],
                          capture_output=True, text=True)
    result = None
    if proc.returncode == 0:
        result = json.loads((Path(out_dir) / "result.json").read_text())
    return proc, result


def finding_ids(result):
    return {f["id"] for f in result["findings"]}


class TestExample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.runs = {}
        for name in ("experiment", "experiment-broken"):
            d = EXAMPLE / name
            t0 = time.perf_counter()
            proc, result = run(["--policy", d / "contact-policy.toml", "--assignments", d / "assignments.csv",
                                "--sends", d / "sends.csv", "--outcomes", d / "outcomes.csv",
                                "--outcome", "converted", "--emit-user-file"], cls.out / name)
            cls.runs[name] = (proc, result, time.perf_counter() - t0)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_runs_fast_and_cleanly(self):
        for name, (proc, _, seconds) in self.runs.items():
            self.assertEqual(proc.returncode, 0, f"{name}: {proc.stderr}")
            self.assertLess(seconds, 10, name)

    def test_required_keys(self):
        for name, (_, r, _) in self.runs.items():
            for key in ("schema_version", "reach", "sends_by_state", "budget", "violations",
                        "termination", "staleness", "findings"):
                self.assertIn(key, r, name)
            for key in ("eligible", "timely", "policy_coverage", "delivered", "all_assigned"):
                self.assertIn(key, r["reach"], name)
            for key in ("cap", "spacing", "control_contacted"):
                self.assertIn("count", r["violations"][key])
            for key in ("p50_hours", "p90_hours", "max_hours"):
                self.assertIn(key, r["staleness"])
            for row in r["sends_by_state"]:
                for key in ("state", "sends", "share", "is_success"):
                    self.assertIn(key, row)

    def test_good_experiment(self):
        truth = KEY["experiment"]
        r = self.runs["experiment"][1]
        self.assertEqual(r["reach"]["gate"], truth["reach_gate"])
        self.assertLessEqual(r["budget"]["success_state_send_share"], truth["success_state_send_share_max"])
        self.assertEqual(r["violations"]["cap"]["count"], truth["cap_violations"])
        self.assertEqual(r["violations"]["spacing"]["count"], truth["spacing_violations"])
        self.assertEqual(r["violations"]["control_contacted"]["count"], truth["control_contacted"])
        self.assertNotIn("reach_gate", finding_ids(r))
        self.assertNotIn("stale_render", finding_ids(r))

    def test_broken_experiment(self):
        truth = KEY["experiment-broken"]
        r = self.runs["experiment-broken"][1]
        self.assertEqual(r["reach"]["gate"], truth["reach_gate"])
        self.assertGreaterEqual(r["budget"]["success_state_send_share"], truth["success_state_send_share_min"])
        self.assertGreaterEqual(r["violations"]["cap"]["count"], truth["cap_violations_min"])
        self.assertGreaterEqual(r["violations"]["spacing"]["count"], truth["spacing_violations_min"])
        self.assertGreaterEqual(r["violations"]["control_contacted"]["count"], truth["control_contacted_min"])
        self.assertGreaterEqual(r["staleness"]["p50_hours"], truth["stale_render_hours_p50_min"])
        self.assertTrue({"reach_gate", "success_state_sends", "cap_violation", "spacing_violation",
                         "control_contacted", "no_send_state_sends", "stale_render"} <= finding_ids(r))

    def test_termination_covers_every_eligible_treatment_user(self):
        for name, (_, r, _) in self.runs.items():
            t = r["termination"]
            self.assertEqual(sum(t["classes"].values()), r["reach"]["treatment_eligible"], name)

    def test_user_file(self):
        with (self.out / "experiment" / "users.csv").open() as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), self.runs["experiment"][1]["inputs"]["assigned_users"])
        self.assertEqual(set(rows[0]), {"user_id", "arm", "termination", "successful_sends",
                                        "first_contact_hours"})

    def test_reports_never_contain_user_ids(self):
        for name in self.runs:
            for f in ("report.md", "result.json"):
                text = (self.out / name / f).read_text()
                self.assertIsNone(re.search(r"\bu_\d{5}\b", text), f"{name}/{f} leaks a user id")

    def test_report_headline_and_sections(self):
        text = (self.out / "experiment-broken" / "report.md").read_text()
        self.assertIn("Reach gate: FAIL", text)
        self.assertIn("of sends went to users already in a success state", text)
        heads = ["## Headline", "## 1. Reach", "## 2. Where the sends went", "## 3. Contact-policy violations",
                 "## 4. Sends per", "## 5. How each sequence ended", "## 6. Render-to-send", "## 7. What to fix"]
        positions = [text.index(h) for h in heads]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Reach gate: PASS", (self.out / "experiment" / "report.md").read_text())


POLICY = """
[policy]
max_sends_per_user = 3
min_hours_between_sends = 24
first_contact_sla_hours = 48
treatment_reach_min = 0.90
control_contact_allowed = {allowed}

[states]
success = ["ACTIVE"]
no_send = ["ACTIVE", "EXCLUDED"]
"""


class TestSmallInputs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_csv(self, name, header, rows):
        path = self.dir / name
        with path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        return path

    def audit(self, assignments, sends, outcomes=None, allowed="false", as_of=None,
              send_header=("user_id", "sent_at", "status", "state_at_send")):
        policy = self.dir / "contact-policy.toml"
        policy.write_text(POLICY.format(allowed=allowed))
        a = self.write_csv("assignments.csv", ["user_id", "arm", "assigned_at", "eligible"], assignments)
        s = self.write_csv("sends.csv", list(send_header), sends)
        args = ["--policy", policy, "--assignments", a, "--sends", s, "--emit-user-file"]
        if outcomes is not None:
            o = self.write_csv("outcomes.csv", ["user_id", "converted"], outcomes)
            args += ["--outcomes", o, "--outcome", "converted"]
        if as_of is not None:
            args += ["--as-of", as_of]
        return run(args, self.dir / "out")

    def user_file(self):
        with (self.dir / "out" / "users.csv").open() as fh:
            return {r["user_id"]: r for r in csv.DictReader(fh)}

    def test_reach_sla_arithmetic(self):
        as_of = iso(9 * 24)
        assignments = [
            ["t1", "treatment", iso(0), "1"],
            ["t2", "treatment", iso(0), "1"],
            ["t3", "treatment", iso(0), "1"],
            ["t4", "treatment", iso(0), "1"],
            ["t5", "treatment", iso(0), "1"],
            ["t6", "treatment", iso(0), "0"],             # not eligible: outside the gate
            ["t7", "treatment", iso(9 * 24 - 47), "1"],   # SLA not elapsed by as_of: outside the gate
            ["c1", "control", iso(0), "1"],
        ]
        sends = [
            ["t1", iso(48), "sent", "NO_GOAL"],                  # exactly at the SLA: reached
            ["t2", iso(48 + 1 / 60), "sent", "NO_GOAL"],         # one minute late
            ["t3", iso(1), "not_needed", "ACTIVE"],              # not_needed counts as reached
            ["t4", iso(2), "failed", "NO_GOAL"],                 # only a failed row
            ["t6", iso(1), "sent", "NO_GOAL"],
            ["t7", iso(9 * 24 - 46), "sent", "NO_GOAL"],
        ]
        proc, r = self.audit(assignments, sends, as_of=as_of)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        reach = r["reach"]
        self.assertEqual(reach["eligible"], 5)
        self.assertEqual(reach["timely"], 2)
        self.assertAlmostEqual(reach["policy_coverage"], 0.4)
        self.assertEqual(reach["gate"], "fail")
        self.assertEqual(reach["sla_not_elapsed"], 1)
        nc = reach["non_contact"]
        self.assertEqual((nc["no_rows"], nc["only_not_delivered"], nc["late_first_contact"]), (1, 1, 1))
        self.assertEqual(reach["delivered"]["users"], 2)                  # t1 and t2
        self.assertEqual(reach["all_assigned"]["denominator"], 6)         # t1..t6
        self.assertEqual(reach["all_assigned"]["users"], 3)               # t1, t3, t6
        self.assertIn("reach_gate", finding_ids(r))
        self.assertAlmostEqual(float(self.user_file()["t2"]["first_contact_hours"]), 48.02, places=2)

    def test_reach_passes_with_not_needed(self):
        assignments = [[f"t{i}", "treatment", iso(0), "1"] for i in range(10)]
        sends = [[f"t{i}", iso(5), "not_needed" if i % 2 else "delivered", "NO_GOAL"] for i in range(9)]
        proc, r = self.audit(assignments, sends, as_of=iso(100))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(r["reach"]["timely"], 9)
        self.assertEqual(r["reach"]["gate"], "pass")                     # 0.9 >= 0.90
        self.assertNotIn("reach_gate", finding_ids(r))

    def test_spacing_and_cap_edges(self):
        assignments = [["s1", "treatment", iso(0), "1"], ["s2", "treatment", iso(0), "1"],
                       ["s3", "treatment", iso(0), "1"]]
        sends = [
            ["s1", iso(1), "sent", "NO_GOAL"], ["s1", iso(25), "sent", "NO_GOAL"],   # gaps exactly 24h
            ["s1", iso(49), "delivered", "NO_GOAL"],                                 # exactly the cap
            ["s1", iso(50), "failed", "NO_GOAL"],                                    # failed: not a send
            ["s2", iso(1), "sent", "NO_GOAL"], ["s2", iso(24.9), "sent", "NO_GOAL"],  # 23.9h gap
            ["s3", iso(1), "sent", "NO_GOAL"], ["s3", iso(31), "sent", "NO_GOAL"],
            ["s3", iso(61), "sent", "NO_GOAL"], ["s3", iso(91), "sent", "NO_GOAL"],  # 4 sends: over cap
        ]
        proc, r = self.audit(assignments, sends)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        v = r["violations"]
        self.assertEqual(v["spacing"]["count"], 1)
        self.assertEqual(v["spacing"]["users"], 1)
        self.assertAlmostEqual(v["spacing"]["shortest_gap_hours"], 23.9, places=6)
        self.assertEqual(v["cap"]["count"], 1)
        self.assertEqual(v["cap"]["max_sends"], 4)
        self.assertEqual(r["sends_per_user"]["distribution"], {"0": 0, "1": 0, "2": 1, "3": 1, "4": 1, "5+": 0})
        term = {uid: row["termination"] for uid, row in self.user_file().items()}
        self.assertEqual(term, {"s1": "budget_complete", "s2": "stopped_early", "s3": "over_cap"})
        self.assertTrue({"cap_violation", "spacing_violation"} <= finding_ids(r))
        for text in v["spacing"]["examples"] + v["cap"]["examples"]:
            self.assertNotRegex(text, r"\bs[123]\b")

    def test_control_contact(self):
        assignments = [["t1", "treatment", iso(0), "1"], ["c1", "control", iso(0), "1"],
                       ["c2", "control", iso(0), "1"]]
        sends = [["t1", iso(2), "sent", "NO_GOAL"], ["c1", iso(3), "sent", "NO_GOAL"],
                 ["c2", iso(3), "failed", "NO_GOAL"]]
        proc, r = self.audit(assignments, sends)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(r["violations"]["control_contacted"]["count"], 1)     # failed rows don't count
        self.assertIn("control_contacted", finding_ids(r))
        self.assertEqual(r["budget"]["successful_sends"], 1)                  # control sends are not budget
        proc, r = self.audit(assignments, sends, allowed="true")
        self.assertEqual(r["violations"]["control_contacted"]["count"], 1)
        self.assertNotIn("control_contacted", finding_ids(r))

    def test_arms_only_from_assignments(self):
        assignments = [["t1", "treatment", iso(0), "1"]]
        sends = [["t1", iso(2), "sent", "NO_GOAL", "control"], ["ghost", iso(2), "sent", "NO_GOAL", "treatment"]]
        proc, r = self.audit(assignments, sends,
                             send_header=("user_id", "sent_at", "status", "state_at_send", "arm"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(r["violations"]["control_contacted"]["count"], 0)
        self.assertEqual(r["budget"]["successful_sends"], 1)
        self.assertTrue(any("not in assignments.csv" in n for n in r["notes"]))

    def test_termination_precedence(self):
        users = ["n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8"]
        assignments = [[u, "treatment", iso(0), "1"] for u in users]

        def series(uid, k, state="NO_GOAL"):
            return [[uid, iso(1 + 30 * i), "sent", state] for i in range(k)]

        sends = ([["n1", iso(1), "failed", "NO_GOAL"]]          # never_contacted even though converted
                 + series("n2", 4)                              # converted beats over_cap
                 + series("n3", 4)                              # over_cap
                 + series("n4", 3)                              # budget_complete
                 + [["n5", iso(1), "not_needed", "ACTIVE"]]      # success_reached via not_needed
                 + series("n6", 1, "ACTIVE")                     # success_reached via last send state
                 + series("n7", 1)                               # stopped_early
                 + series("n8", 1) + [["n8", iso(40), "not_needed", "ACTIVE"]])
        outcomes = [["n1", "1"], ["n2", "1"], ["n3", "0"], ["n4", ""], ["n5", "0"], ["n6", "0"],
                    ["n7", "0"], ["n8", "0"]]
        proc, r = self.audit(assignments, sends, outcomes=outcomes)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        term = {uid: row["termination"] for uid, row in self.user_file().items()}
        self.assertEqual(term, {"n1": "never_contacted", "n2": "converted", "n3": "over_cap",
                                "n4": "budget_complete", "n5": "success_reached", "n6": "success_reached",
                                "n7": "stopped_early", "n8": "success_reached"})
        self.assertEqual(r["termination"]["outcome_blank"], 1)
        self.assertEqual(r["budget"]["success_state_sends"], 1)
        self.assertIn("success_state_sends", finding_ids(r))
        self.assertIn("no_send_state_sends", finding_ids(r))
        # Without outcomes, converted is never assigned and n2 falls through to over_cap.
        proc, r = self.audit(assignments, sends)
        self.assertEqual(self.user_file()["n2"]["termination"], "over_cap")
        self.assertEqual(r["termination"]["classes"]["converted"], 0)

    def test_staleness(self):
        assignments = [["t1", "treatment", iso(0), "1"], ["t2", "treatment", iso(0), "1"]]
        header = ("user_id", "sent_at", "status", "state_at_send", "rendered_at")
        fresh = [["t1", iso(2), "sent", "NO_GOAL", iso(1.9)], ["t2", iso(2), "sent", "NO_GOAL", iso(1.8)]]
        proc, r = self.audit(assignments, fresh, send_header=header)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertAlmostEqual(r["staleness"]["max_hours"], 0.2, places=6)
        self.assertNotIn("stale_render", finding_ids(r))
        one_old = [["t1", iso(2), "sent", "NO_GOAL", iso(1.9)], ["t1", iso(40), "sent", "NO_GOAL", iso(39.9)],
                   ["t2", iso(30), "sent", "NO_GOAL", iso(5)]]          # 25h old: max > 24h
        proc, r = self.audit(assignments, one_old, send_header=header)
        self.assertAlmostEqual(r["staleness"]["p50_hours"], 0.1, places=6)
        self.assertIn("stale_render", finding_ids(r))
        proc, r = self.audit(assignments, [["t1", iso(2), "sent", "NO_GOAL"]])
        self.assertIsNone(r["staleness"])

    def test_missing_column_exits_2(self):
        policy = self.dir / "contact-policy.toml"
        policy.write_text(POLICY.format(allowed="false"))
        a = self.write_csv("assignments.csv", ["user_id", "arm"], [["t1", "treatment"]])
        s = self.write_csv("sends.csv", ["user_id", "sent_at", "status"], [])
        proc, _ = run(["--policy", policy, "--assignments", a, "--sends", s], self.dir / "out")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("assignments.csv", proc.stderr)
        self.assertIn("assigned_at", proc.stderr)

    def test_bad_status_exits_2_with_row(self):
        proc, _ = self.audit([["t1", "treatment", iso(0), "1"]], [["t1", iso(1), "opened", "NO_GOAL"]])
        self.assertEqual(proc.returncode, 2)
        self.assertIn("sends.csv:2", proc.stderr)
        self.assertIn("status", proc.stderr)

    def test_bad_policy_exits_2_with_key(self):
        policy = self.dir / "contact-policy.toml"
        policy.write_text("[policy]\nmax_sends_per_user = 3\n")
        a = self.write_csv("assignments.csv", ["user_id", "arm", "assigned_at"], [["t1", "treatment", iso(0)]])
        s = self.write_csv("sends.csv", ["user_id", "sent_at", "status"], [])
        proc, _ = run(["--policy", policy, "--assignments", a, "--sends", s], self.dir / "out")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("contact-policy.toml:policy.min_hours_between_sends", proc.stderr)

    def test_help_explains_every_flag(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        for flag in ("--policy", "--assignments", "--sends", "--outcomes", "--outcome", "--as-of",
                     "--emit-user-file", "--out"):
            self.assertIn(flag, proc.stdout)


if __name__ == "__main__":
    unittest.main()
