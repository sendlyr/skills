"""End-to-end tests for skills/designing-holdout-experiments/scripts/holdout.py."""

import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "designing-holdout-experiments" / "scripts" / "holdout.py"
EXAMPLES = ROOT / "examples" / "practica"
ANSWER_KEY = json.loads((EXAMPLES / "answer_key.json").read_text(encoding="utf-8"))


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def size(self, *args):
        out = self.tmp / f"size{len(list(self.tmp.iterdir()))}"
        r = run("size", *args, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads((out / "result.json").read_text(encoding="utf-8")), r.stdout


class TestSize(TempDirCase):
    def test_textbook_values(self):
        # Fleiss (no continuity correction), two-sided alpha 0.05, power 0.8.
        cases = [((0.30, 0.05), 1377), ((0.10, 0.02), 3841), ((0.50, 0.10), 388)]
        for (baseline, mde), expected in cases:
            res, _ = self.size("--baseline", baseline, "--mde", mde)
            self.assertEqual(res["n_control"], expected, (baseline, mde))
            self.assertEqual(res["n_treatment"], expected)
            self.assertEqual(res["n_total"], 2 * expected)
            self.assertNotIn("weeks", res)

    def test_practica_example_sentence_and_weeks(self):
        res, out = self.size("--baseline", 0.23, "--mde", 0.02, "--eligible-per-week", 300)
        self.assertEqual(res["n_control"], 7157)
        self.assertEqual(res["n_total"], 14314)
        self.assertEqual(res["weeks"], 48)                    # ceil(14314 / 300)
        self.assertIn("To detect a rise from 23.0% to 25.0% (+2.0pp) with 80% power at α = 0.05, you need "
                      "7,157 users per arm (14,314 total), about 48 weeks at 300 eligible users a week.", out)
        self.assertIn("This is a slow fixed experiment, not an optimisation loop", out)
        self.assertEqual(len(res["warnings"]), 1)

    def test_no_slow_warning_for_fast_experiment(self):
        res, out = self.size("--baseline", 0.23, "--mde", 0.02, "--eligible-per-week", 5000)
        self.assertEqual(res["weeks"], 3)
        self.assertNotIn("slow fixed experiment", out)

    def test_sensitivity(self):
        res, out = self.size("--baseline", 0.23, "--mde", 0.02, "--eligible-per-week", 300)
        rows = res["sensitivity"]
        self.assertEqual([r["multiplier"] for r in rows], [0.5, 1.0, 1.5, 2.0])
        self.assertEqual(rows[1]["n_control"], res["n_control"])
        totals = [r["n_total"] for r in rows]
        self.assertEqual(totals, sorted(totals, reverse=True))
        self.assertTrue(3.5 < rows[0]["n_control"] / rows[1]["n_control"] < 4.5)   # half the effect, ~4x users
        self.assertTrue(3.5 < rows[1]["n_control"] / rows[3]["n_control"] < 4.5)
        self.assertIn("## Sensitivity", out)
        self.assertIn("+1.0pp (0.5× target)", out)

    def test_decrease_and_unequal_allocation(self):
        res, out = self.size("--baseline", 0.23, "--mde", 0.02, "--direction", "decrease")
        self.assertAlmostEqual(res["target_rate"], 0.21)
        self.assertIn("To detect a fall from 23.0% to 21.0% (-2.0pp)", out)
        res, out = self.size("--baseline", 0.23, "--mde", 0.02, "--allocation", 0.3)
        self.assertGreater(res["n_control"], res["n_treatment"])
        self.assertIn("control users and", out)

    def test_bad_input_exits_2(self):
        r = run("size", "--baseline", 23, "--mde", 0.02)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--baseline", r.stderr)
        r = run("size", "--baseline", 0.99, "--mde", 0.05)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--mde", r.stderr)

    def test_help_explains_flags(self):
        r = run("size", "--help")
        self.assertEqual(r.returncode, 0)
        for flag in ("--baseline", "--mde", "--direction", "--alpha", "--power", "--allocation",
                     "--eligible-per-week", "--out"):
            self.assertIn(flag, r.stdout)
        for cmd in ("assign", "seal", "verify"):
            self.assertEqual(run(cmd, "--help").returncode, 0)


class TestAssign(TempDirCase):
    def test_reproduces_example_arms(self):
        src = EXAMPLES / "experiment" / "assignments.csv"
        key = ANSWER_KEY["designing-holdout-experiments"]
        out = self.tmp / "assignments.csv"
        report = self.tmp / "report"
        r = run("assign", "--users", src, "--salt", key["salt"], "--allocation", key["allocation_treatment"],
                "--out", out, "--report-dir", report)
        self.assertEqual(r.returncode, 0, r.stderr)
        expected = {row["user_id"]: row for row in read_rows(src)}
        got = {row["user_id"]: row for row in read_rows(out)}
        self.assertEqual(set(got), set(expected))
        mismatched = [u for u in expected if expected[u]["arm"] != got[u]["arm"]]
        self.assertEqual(mismatched, [])
        # assigned_at and eligibility are carried over from the input.
        self.assertTrue(all(got[u]["assigned_at"] == expected[u]["assigned_at"] for u in expected))
        self.assertTrue(all(got[u]["eligible"] == expected[u]["eligible"] for u in expected))
        res = json.loads((report / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(res["counts"]["treatment"], ANSWER_KEY["experiment_counts"]["treatment"])
        self.assertEqual(res["counts"]["control"], ANSWER_KEY["experiment_counts"]["control"])
        self.assertEqual(res["input_arm_disagreements"], 0)
        self.assertGreater(res["srm_p"], 0.001)
        self.assertIn("Sample-ratio check", r.stdout)
        self.assertNotIn("u_0", (report / "report.md").read_text(encoding="utf-8"))

    def test_deterministic_and_never_redrawn(self):
        users = self.tmp / "users.csv"
        users.write_text("user_id\n" + "".join(f"x{i}\n" for i in range(200)), encoding="utf-8")
        out = self.tmp / "a.csv"
        r1 = run("assign", "--users", users, "--salt", "s1", "--assigned-at", "2026-01-01T00:00:00Z", "--out", out)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        first = out.read_text(encoding="utf-8")
        # Re-running (even with a different default time) keeps every arm and assignment time.
        r2 = run("assign", "--users", users, "--salt", "s1", "--out", out)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertEqual(out.read_text(encoding="utf-8"), first)
        # A different salt would re-draw: refused, and the file is untouched.
        r3 = run("assign", "--users", users, "--salt", "s2", "--out", out)
        self.assertEqual(r3.returncode, 2)
        self.assertIn("never re-drawn", r3.stderr)
        self.assertEqual(out.read_text(encoding="utf-8"), first)
        # Every row matches the contract hash.
        for row in read_rows(out):
            u = int(hashlib.sha256(f"s1::{row['user_id']}".encode()).hexdigest()[:13], 16) / 16 ** 13
            self.assertEqual(row["arm"], "treatment" if u < 0.5 else "control")
            self.assertEqual(row["assigned_at"], "2026-01-01T00:00:00Z")

    def test_stratum(self):
        users = self.tmp / "users.csv"
        lines = ["user_id,plan"] + [f"y{i},{'monthly' if i % 2 else 'yearly'}" for i in range(300)]
        users.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out = self.tmp / "a.csv"
        report = self.tmp / "report"
        r = run("assign", "--users", users, "--salt", "s", "--stratum-column", "plan",
                "--assigned-at", "2026-01-01", "--out", out, "--report-dir", report)
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = read_rows(out)
        self.assertEqual(list(rows[0]), ["user_id", "arm", "assigned_at", "stratum"])
        for row in rows:
            u = int(hashlib.sha256(f"s:{row['stratum']}:{row['user_id']}".encode()).hexdigest()[:13], 16) / 16 ** 13
            self.assertEqual(row["arm"], "treatment" if u < 0.5 else "control")
        res = json.loads((report / "result.json").read_text(encoding="utf-8"))
        by = res["counts"]["by_stratum"]
        self.assertEqual(set(by), {"monthly", "yearly"})
        self.assertEqual(sum(by[s]["treatment"] + by[s]["control"] for s in by), 300)
        self.assertIn("By stratum", r.stdout)

    def test_duplicate_user_exits_2(self):
        users = self.tmp / "users.csv"
        users.write_text("user_id\na\nb\na\n", encoding="utf-8")
        r = run("assign", "--users", users, "--salt", "s", "--out", self.tmp / "a.csv")
        self.assertEqual(r.returncode, 2)
        self.assertIn("users.csv:4", r.stderr)


class TestSealVerify(TempDirCase):
    def copy_prereg(self):
        dst = self.tmp / "prereg.toml"
        shutil.copy(EXAMPLES / "experiment" / "prereg.toml", dst)
        return dst

    def test_example_locks_verify(self):
        for folder in ("experiment", "experiment-broken"):
            r = run("verify", EXAMPLES / folder / "prereg.toml")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("MATCH", r.stdout)

    def test_round_trip(self):
        prereg = self.copy_prereg()
        out = self.tmp / "seal-report"
        r = run("seal", prereg, "--sealed-at", "2026-05-08T09:00:00Z", "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        lock = json.loads((self.tmp / "prereg.lock").read_text(encoding="utf-8"))
        self.assertEqual(set(lock), {"file", "sha256", "sealed_at"})
        self.assertEqual(lock["file"], "prereg.toml")
        self.assertEqual(lock["sealed_at"], "2026-05-08T09:00:00Z")
        # Same bytes as the example, so the same lock as the example.
        example_lock = json.loads((EXAMPLES / "experiment" / "prereg.lock").read_text(encoding="utf-8"))
        self.assertEqual(lock["sha256"], example_lock["sha256"])
        self.assertEqual((self.tmp / "prereg.lock").read_text(encoding="utf-8"),
                         (EXAMPLES / "experiment" / "prereg.lock").read_text(encoding="utf-8"))
        res = json.loads((out / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(res["sha256"], lock["sha256"])
        self.assertTrue(res["match"])
        v = run("verify", prereg, "--out", self.tmp / "verify-report")
        self.assertEqual(v.returncode, 0, v.stdout)
        vres = json.loads((self.tmp / "verify-report" / "result.json").read_text(encoding="utf-8"))
        self.assertTrue(vres["match"])
        self.assertEqual(vres["sha256"], lock["sha256"])

    def test_line_endings_are_normalised(self):
        prereg = self.copy_prereg()
        text = prereg.read_text(encoding="utf-8")
        prereg.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        self.assertEqual(run("seal", prereg).returncode, 0)
        lock = json.loads((self.tmp / "prereg.lock").read_text(encoding="utf-8"))
        self.assertEqual(lock["sha256"], hashlib.sha256(text.encode("utf-8")).hexdigest())

    def test_refuses_without_minimum_worthwhile_effect(self):
        prereg = self.copy_prereg()
        text = prereg.read_text(encoding="utf-8")
        prereg.write_text("\n".join(l for l in text.splitlines() if not l.startswith("minimum_worthwhile_effect"))
                          + "\n", encoding="utf-8")
        r = run("seal", prereg)
        self.assertEqual(r.returncode, 2)
        self.assertIn("primary.minimum_worthwhile_effect", r.stderr)
        self.assertIn("cannot be falsified", r.stderr)
        self.assertFalse((self.tmp / "prereg.lock").exists())

    def test_refuses_zero_effect_and_missing_gates(self):
        prereg = self.copy_prereg()
        text = prereg.read_text(encoding="utf-8")
        prereg.write_text(text.replace("minimum_worthwhile_effect = 0.03", "minimum_worthwhile_effect = 0")
                          .replace("srm_p_min = 0.001\n", ""), encoding="utf-8")
        r = run("seal", prereg)
        self.assertEqual(r.returncode, 2)
        self.assertIn("cannot be falsified", r.stderr)
        self.assertIn("gates.srm_p_min", r.stderr)
        self.assertFalse((self.tmp / "prereg.lock").exists())

    def test_refuses_overwrite_without_force(self):
        prereg = self.copy_prereg()
        self.assertEqual(run("seal", prereg, "--sealed-at", "2026-05-08T09:00:00Z").returncode, 0)
        before = (self.tmp / "prereg.lock").read_text(encoding="utf-8")
        r = run("seal", prereg)
        self.assertEqual(r.returncode, 2)
        self.assertIn("protocol deviation", r.stderr)
        self.assertEqual((self.tmp / "prereg.lock").read_text(encoding="utf-8"), before)
        r = run("seal", prereg, "--force", "--sealed-at", "2026-05-09T09:00:00Z")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("protocol deviation", r.stdout)
        self.assertIn("2026-05-09T09:00:00Z", (self.tmp / "prereg.lock").read_text(encoding="utf-8"))

    def test_tampered_file_fails_verify(self):
        prereg = self.copy_prereg()
        self.assertEqual(run("seal", prereg).returncode, 0)
        prereg.write_text(prereg.read_text(encoding="utf-8").replace("minimum_worthwhile_effect = 0.03",
                                                                     "minimum_worthwhile_effect = 0.01"),
                          encoding="utf-8")
        r = run("verify", prereg)
        self.assertEqual(r.returncode, 1)
        self.assertIn("MISMATCH", r.stdout)

    def test_missing_lock_fails_verify(self):
        prereg = self.copy_prereg()
        r = run("verify", prereg)
        self.assertEqual(r.returncode, 1)
        self.assertIn("NOT SEALED", r.stdout)


if __name__ == "__main__":
    unittest.main()
