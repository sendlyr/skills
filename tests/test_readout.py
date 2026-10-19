"""End-to-end tests for skills/writing-decision-readouts/scripts/readout.py."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "writing-decision-readouts" / "scripts" / "readout.py"
EXAMPLES = ROOT / "examples" / "practica"
ANSWER_KEY = json.loads((EXAMPLES / "answer_key.json").read_text(encoding="utf-8"))["writing-decision-readouts"]
EXAMPLE_AS_OF = "2026-07-15"          # the generator's extraction date for the experiment data

ITT_STATEMENT = ("This readout compares arms as randomised (intent-to-treat). It never compares contacted "
                 "against uncontacted users, because being contacted is not random.")
HIDDEN = ("hidden until the cohort is valid and mature, to prevent stopping early or changing the question "
          "after seeing the answer")
SECTIONS = ["Verdict", "Delivery integrity", "Assignment and data health", "Definition",
            "Primary outcome by arm", "Mechanism", "Strata", "Limitations", "Decision record"]
GATE_IDS = ["srm", "treatment_reach", "control_contacted", "prereg_hash", "missing_outcomes", "maturity"]

PREREG = """\
[experiment]
name = "constructed-test"
hypothesis = "The policy moves the primary outcome."
mechanism = "Users perform the behaviour more often."
unit = "user"
allocation_treatment = 0.5
cohort_start = "2026-01-01"
cohort_end = "2026-01-31"
analysis_not_before = "2026-03-01"

[primary]
metric = "{metric}"
baseline_rate = {baseline}
minimum_worthwhile_effect = {delta}
direction = "{direction}"
confidence_level = 0.95
{mechanism}
[gates]
treatment_reach_min = 0.90
first_contact_sla_hours = 48
max_missing_outcome_share = 0.05
srm_p_min = 0.001
control_contact_allowed = false
"""


def sections(report):
    """Split report.md into {number: text} by its '## N. Title' headings."""
    parts = re.split(r"^## (\d+)\. .*$", report, flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


def build(folder, groups, *, metric="converted", baseline=0.30, delta=0.05, direction="increase",
          mechanism=False, control_sends=0):
    """Write a tiny experiment. groups: dicts with arm, n, k, and optional mech_k, blank, stratum."""
    folder.mkdir(parents=True, exist_ok=True)
    has_stratum = any("stratum" in g for g in groups)
    start = datetime(2026, 1, 5, tzinfo=timezone.utc)
    assign = ["user_id,arm,assigned_at,eligible" + (",stratum" if has_stratum else "")]
    outcomes = [f"user_id,{metric}" + (",behaviour" if mechanism else "")]
    sends = ["user_id,sent_at,status"]
    idx = 0
    contaminated = 0
    for g in groups:
        for j in range(g["n"]):
            idx += 1
            uid = f"zz_{idx:05d}"
            at = start + timedelta(minutes=idx)
            iso = at.strftime("%Y-%m-%dT%H:%M:%SZ")
            assign.append(f"{uid},{g['arm']},{iso},1" + (f",{g.get('stratum', '')}" if has_stratum else ""))
            blank = j >= g["n"] - g.get("blank", 0)
            value = "" if blank else ("1" if j < g["k"] else "0")
            mech = "" if blank else ("1" if j < g.get("mech_k", 0) else "0")
            outcomes.append(f"{uid},{value}" + (f",{mech}" if mechanism else ""))
            sent = (at + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            if g["arm"] == "treatment":
                sends.append(f"{uid},{sent},sent")
            elif contaminated < control_sends:
                contaminated += 1
                sends.append(f"{uid},{sent},sent")
    (folder / "assignments.csv").write_text("\n".join(assign) + "\n", encoding="utf-8")
    (folder / "outcomes.csv").write_text("\n".join(outcomes) + "\n", encoding="utf-8")
    (folder / "sends.csv").write_text("\n".join(sends) + "\n", encoding="utf-8")
    mech_block = '\n[mechanism]\nmetric = "behaviour"\n' if mechanism else ""
    (folder / "prereg.toml").write_text(PREREG.format(metric=metric, baseline=baseline, delta=delta,
                                                      direction=direction, mechanism=mech_block),
                                        encoding="utf-8")
    return folder


class ReadoutCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def readout(self, folder, *, sends=True, as_of="2026-03-15", expect_code=0, extra=()):
        out = self.tmp / f"out{len(list(self.tmp.glob('out*')))}"
        args = [sys.executable, str(SCRIPT), "--prereg", folder / "prereg.toml",
                "--assignments", folder / "assignments.csv", "--outcomes", folder / "outcomes.csv",
                "--out", out, *extra]
        if sends:
            args += ["--sends", folder / "sends.csv"]
        if as_of:
            args += ["--as-of", as_of]
        r = subprocess.run([str(a) for a in args], capture_output=True, text=True)
        self.assertEqual(r.returncode, expect_code, r.stderr)
        if expect_code != 0:
            return None, None, r
        result = json.loads((out / "result.json").read_text(encoding="utf-8"))
        report = (out / "report.md").read_text(encoding="utf-8")
        self.assertEqual(r.stdout.strip(), report.strip())
        self.check_report_rules(report, result)
        return result, report, r

    def check_report_rules(self, report, result):
        titles = re.findall(r"^## (\d+)\. (.*)$", report, flags=re.M)
        self.assertEqual([int(n) for n, _ in titles], list(range(1, 10)))
        self.assertEqual([t for _, t in titles], SECTIONS)
        self.assertEqual(report.count(ITT_STATEMENT), 1)
        secs = sections(report)
        for n in (5, 6, 7):
            body = secs[n].replace(ITT_STATEMENT, "")
            self.assertNotIn("contacted", body.lower(), f"section {n} mentions contact status")
        low = report.lower()
        self.assertNotIn("per-protocol", low)
        self.assertNotIn("per protocol", low)
        self.assertNotRegex(report, r"\b(u|zz)_\d{5}\b")          # never a user ID
        self.assertEqual([g["id"] for g in result["gates"]], GATE_IDS)
        for g in result["gates"]:
            self.assertEqual({"id", "passed", "value", "threshold", "message"} - set(g), set())
        self.assertIn(f"**Verdict: {result['verdict']}**", secs[1])
        for key in ("schema_version", "verdict", "gates", "cohort", "primary", "mechanism", "reach",
                    "limitations", "decision_record"):
            self.assertIn(key, result)
        for key in ("metric", "treatment", "control", "diff", "diff_ci", "relative", "p_value", "delta_min",
                    "n_required_per_arm"):
            self.assertIn(key, result["primary"])
        self.assertEqual(result["decision_record"]["evidence_class"], result["verdict"])
        if result["verdict"] not in ("SUPPORTED_AT_TARGET", "HARMFUL", "FALSIFIED_AS_WORTHWHILE", "INCONCLUSIVE"):
            self.assertFalse(result["primary"]["feedback_eligible"])
            self.assertIn(HIDDEN, secs[5])
            self.assertNotIn("Difference (treatment", report)
            p = result["primary"]
            for arm in ("treatment", "control"):
                if p[arm]["rate"] is not None:
                    self.assertNotIn(f"| {100 * p[arm]['rate']:.1f}% |", report)
            if p["diff"] is not None:
                self.assertNotIn(f"{100 * p['diff']:+.1f}pp", report)

    def failed(self, result):
        return [g["id"] for g in result["gates"] if not g["passed"]]


class TestExamples(ReadoutCase):
    def test_good_experiment_is_supported(self):
        folder = EXAMPLES / "experiment"
        result, report, _ = self.readout(folder, as_of=EXAMPLE_AS_OF)
        self.assertEqual(result["verdict"], ANSWER_KEY["experiment"]["verdict"])
        self.assertEqual(self.failed(result), [])
        p = result["primary"]
        self.assertGreaterEqual(p["diff_ci"][0], p["delta_min"])
        self.assertEqual(p["metric"], "converted")
        self.assertEqual(p["n_required_per_arm"], 3226)
        self.assertTrue(p["feedback_eligible"])
        self.assertIn("Powered for the registered effect", report)
        self.assertNotIn("NOT POWERED", report)
        self.assertIn("for reference; the decision uses the interval against the pre-registered effect", report)
        self.assertIn("This tells you whether the behaviour moved, not whether the outcome did.", report)
        self.assertGreaterEqual(result["reach"]["timely_reach"], 0.90)
        self.assertEqual(result["reach"]["control_contacted"]["users"], 0)
        self.assertGreater(result["cohort"]["excluded_by_design"]["total"], 0)
        self.assertGreater(result["cohort"]["outside_cohort"]["total"], 0)
        self.assertIn("Difference (treatment − control): +9.1pp", report)

    def test_broken_experiment_refuses_to_learn(self):
        folder = EXAMPLES / "experiment-broken"
        result, report, _ = self.readout(folder, as_of=EXAMPLE_AS_OF)
        self.assertEqual(result["verdict"], ANSWER_KEY["experiment-broken"]["verdict"])
        for gate in ANSWER_KEY["experiment-broken"]["failed_gates_include"]:
            self.assertIn(gate, self.failed(result))
        reach = next(g for g in result["gates"] if g["id"] == "treatment_reach")
        self.assertRegex(report, r"Refused to learn: treatment reach was \d+\.\d% against a pre-registered "
                                 r"90\.0% minimum, so the treatment arm was not reliably treated\. These outcome "
                                 r"numbers cannot revise the product hypothesis\.")
        self.assertLess(reach["value"], 0.9)
        self.assertEqual(result["decision_allowed"], "repair_or_repeat_only")
        # The audit copy keeps the numbers, flagged as not feedback eligible.
        self.assertIsNotNone(result["primary"]["diff"])
        self.assertFalse(result["primary"]["feedback_eligible"])
        self.assertTrue(result["reach"]["gap_windows"])

    def test_default_as_of_is_latest_input_timestamp(self):
        result, report, _ = self.readout(EXAMPLES / "experiment", as_of=None)
        self.assertEqual(result["as_of_source"], "latest timestamp in the inputs")
        self.assertLess(result["as_of"][:10], "2026-07-06")   # before analysis_not_before
        self.assertEqual(result["verdict"], "NOT_READY")

    def test_as_of_before_analysis_date_is_not_ready(self):
        result, report, _ = self.readout(EXAMPLES / "experiment", as_of="2026-07-01")
        self.assertEqual(result["verdict"], "NOT_READY")
        self.assertEqual(self.failed(result), ["maturity"])
        self.assertIn(HIDDEN, report)
        self.assertNotIn("+8.2pp", report)
        self.assertNotIn("31.9%", report)
        self.assertEqual(result["decision_allowed"], "wait")

    def test_tampered_prereg_is_invalid_measurement(self):
        folder = self.tmp / "experiment"
        shutil.copytree(EXAMPLES / "experiment", folder)
        prereg = folder / "prereg.toml"
        prereg.write_text(prereg.read_text(encoding="utf-8").replace("minimum_worthwhile_effect = 0.03",
                                                                     "minimum_worthwhile_effect = 0.01"),
                          encoding="utf-8")
        result, report, _ = self.readout(folder, as_of=EXAMPLE_AS_OF)
        self.assertEqual(result["verdict"], "INVALID_MEASUREMENT")
        self.assertEqual(self.failed(result), ["prereg_hash"])
        self.assertIn("PREREGISTRATION_DRIFT", report)
        self.assertFalse(result["prereg"]["match"])

    def test_unsealed_plan_passes_with_warning(self):
        folder = self.tmp / "experiment"
        shutil.copytree(EXAMPLES / "experiment", folder)
        (folder / "prereg.lock").unlink()
        result, report, _ = self.readout(folder, as_of=EXAMPLE_AS_OF)
        self.assertEqual(result["verdict"], "SUPPORTED_AT_TARGET")
        gate = next(g for g in result["gates"] if g["id"] == "prereg_hash")
        self.assertTrue(gate["passed"])
        self.assertIn("NOT SEALED", gate["message"])
        self.assertTrue(any("not sealed" in x for x in result["limitations"]))

    def test_no_sends_file_is_delivery_unverified(self):
        result, report, _ = self.readout(EXAMPLES / "experiment", sends=False, as_of=EXAMPLE_AS_OF)
        self.assertEqual(result["verdict"], "INVALID_DELIVERY")
        self.assertIn("treatment_reach", self.failed(result))
        reach = next(g for g in result["gates"] if g["id"] == "treatment_reach")
        self.assertIn("delivery unverified", reach["message"])
        self.assertIn("delivery unverified", report)
        self.assertFalse(result["reach"]["verified"])


class TestConstructed(ReadoutCase):
    def test_harmful(self):
        folder = build(self.tmp / "d", [{"arm": "treatment", "n": 400, "k": 120},
                                        {"arm": "control", "n": 400, "k": 200}])
        result, report, _ = self.readout(folder)
        self.assertEqual(result["verdict"], "HARMFUL")
        self.assertLess(result["primary"]["diff_ci"][1], 0)

    def test_falsified_as_worthwhile(self):
        folder = build(self.tmp / "d", [{"arm": "treatment", "n": 2000, "k": 610},
                                        {"arm": "control", "n": 2000, "k": 600}])
        result, report, _ = self.readout(folder)
        self.assertEqual(result["verdict"], "FALSIFIED_AS_WORTHWHILE")
        lo, hi = result["primary"]["diff_ci"]
        self.assertTrue(lo < 0 < hi < 0.05)
        self.assertIn("rule out the effect the hypothesis promised", report)

    def test_inconclusive(self):
        folder = build(self.tmp / "d", [{"arm": "treatment", "n": 100, "k": 33},
                                        {"arm": "control", "n": 100, "k": 30}])
        result, report, _ = self.readout(folder)
        self.assertEqual(result["verdict"], "INCONCLUSIVE")
        lo, hi = result["primary"]["diff_ci"]
        self.assertTrue(lo < 0.05 <= hi)
        self.assertIn("NOT POWERED for the registered effect", report)
        self.assertIn("cannot be relabelled", report)

    def test_srm_is_invalid_assignment(self):
        folder = build(self.tmp / "d", [{"arm": "treatment", "n": 600, "k": 300},
                                        {"arm": "control", "n": 400, "k": 100}])
        result, report, _ = self.readout(folder)
        self.assertEqual(result["verdict"], "INVALID_ASSIGNMENT")
        self.assertIn("srm", self.failed(result))
        self.assertIn("Refused to learn", report)

    def test_precedence_lists_every_failure(self):
        # SRM, delivery (no sends) and maturity all fail; assignment names the verdict.
        folder = build(self.tmp / "d", [{"arm": "treatment", "n": 600, "k": 300},
                                        {"arm": "control", "n": 400, "k": 100}])
        result, report, _ = self.readout(folder, sends=False, as_of="2026-02-01")
        self.assertEqual(result["verdict"], "INVALID_ASSIGNMENT")
        self.assertEqual(self.failed(result), ["srm", "treatment_reach", "control_contacted", "maturity"])

    def test_control_contamination_is_invalid_delivery(self):
        folder = build(self.tmp / "d", [{"arm": "treatment", "n": 400, "k": 200},
                                        {"arm": "control", "n": 400, "k": 100}], control_sends=3)
        result, report, _ = self.readout(folder)
        self.assertEqual(result["verdict"], "INVALID_DELIVERY")
        self.assertEqual(self.failed(result), ["control_contacted"])
        self.assertIn("3 control users were contacted", report)

    def test_missing_outcomes_is_invalid_measurement(self):
        folder = build(self.tmp / "d", [{"arm": "treatment", "n": 400, "k": 200, "blank": 40},
                                        {"arm": "control", "n": 400, "k": 100, "blank": 40}])
        result, report, _ = self.readout(folder)
        self.assertEqual(result["verdict"], "INVALID_MEASUREMENT")
        self.assertEqual(self.failed(result), ["missing_outcomes"])
        self.assertEqual(result["primary"]["treatment"]["blank"], 40)

    def test_direction_decrease(self):
        groups = [{"arm": "treatment", "n": 400, "k": 100}, {"arm": "control", "n": 400, "k": 200}]
        down = build(self.tmp / "down", groups, metric="churned", baseline=0.4, direction="decrease")
        result, report, _ = self.readout(down)
        self.assertEqual(result["verdict"], "SUPPORTED_AT_TARGET")
        self.assertAlmostEqual(result["primary"]["diff"], -0.25)
        self.assertAlmostEqual(result["primary"]["directional_diff"], 0.25)
        self.assertIn("Lower is better", report)
        up = build(self.tmp / "up", groups, metric="churned", baseline=0.4, direction="increase")
        result, _, _ = self.readout(up)
        self.assertEqual(result["verdict"], "HARMFUL")

    def test_mechanism_moved_but_outcome_did_not(self):
        folder = build(self.tmp / "d", [{"arm": "treatment", "n": 1000, "k": 301, "mech_k": 420},
                                        {"arm": "control", "n": 1000, "k": 300, "mech_k": 300}], mechanism=True)
        result, report, _ = self.readout(folder)
        self.assertEqual(result["verdict"], "FALSIFIED_AS_WORTHWHILE")
        self.assertTrue(result["mechanism"]["moved"])
        mech = sections(report)[6]
        self.assertIn("This tells you whether the behaviour moved, not whether the outcome did.", mech)
        self.assertIn("The behaviour moved but the outcome did not", mech)

    def test_strata_are_diagnostic(self):
        groups = [{"arm": "treatment", "n": 300, "k": 120, "stratum": "monthly"},
                  {"arm": "control", "n": 300, "k": 90, "stratum": "monthly"},
                  {"arm": "treatment", "n": 200, "k": 60, "stratum": "yearly"},
                  {"arm": "control", "n": 200, "k": 58, "stratum": "yearly"}]
        folder = build(self.tmp / "d", groups)
        result, report, _ = self.readout(folder)
        self.assertEqual(result["verdict"], "INCONCLUSIVE")
        self.assertEqual([s["stratum"] for s in result["strata"]], ["monthly", "yearly"])
        strata = sections(report)[7]
        self.assertIn("Pre-registered strata only; diagnostic, never a basis for choosing a winner after the fact.",
                      strata)
        self.assertIn("| monthly |", strata)
        # Not mature: strata stay, but their differences are hidden.
        result, report, _ = self.readout(folder, as_of="2026-02-15")
        self.assertEqual(result["verdict"], "NOT_READY")
        self.assertIn(HIDDEN, sections(report)[7])
        self.assertNotIn("Control rate", sections(report)[7])


class TestMalformed(ReadoutCase):
    def test_bad_arm_names_file_and_row(self):
        folder = build(self.tmp / "d", [{"arm": "treatment", "n": 5, "k": 1}, {"arm": "control", "n": 5, "k": 1}])
        path = folder / "assignments.csv"
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[2] = lines[2].replace(",treatment,", ",variant,")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _, _, r = self.readout(folder, expect_code=2)
        self.assertIn("assignments.csv:3", r.stderr)

    def test_bad_outcome_value_and_missing_column(self):
        folder = build(self.tmp / "d", [{"arm": "treatment", "n": 5, "k": 1}, {"arm": "control", "n": 5, "k": 1}])
        path = folder / "outcomes.csv"
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[4] = lines[4].rsplit(",", 1)[0] + ",maybe"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _, _, r = self.readout(folder, expect_code=2)
        self.assertIn("outcomes.csv:5", r.stderr)
        path.write_text("user_id,other\nzz_00001,1\n", encoding="utf-8")
        _, _, r = self.readout(folder, expect_code=2)
        self.assertIn("converted", r.stderr)

    def test_prereg_without_effect_exits_2(self):
        folder = build(self.tmp / "d", [{"arm": "treatment", "n": 5, "k": 1}, {"arm": "control", "n": 5, "k": 1}])
        prereg = folder / "prereg.toml"
        prereg.write_text(prereg.read_text(encoding="utf-8").replace("minimum_worthwhile_effect = 0.05\n", ""),
                          encoding="utf-8")
        _, _, r = self.readout(folder, expect_code=2)
        self.assertIn("prereg.toml:primary.minimum_worthwhile_effect", r.stderr)
        self.assertIn("cannot be falsified", r.stderr)

    def test_help_explains_flags(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        for flag in ("--prereg", "--assignments", "--outcomes", "--sends", "--as-of", "--out"):
            self.assertIn(flag, r.stdout)


if __name__ == "__main__":
    unittest.main()
