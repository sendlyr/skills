"""Unit tests for the canonical shared blocks and their copies."""

import importlib.util
import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(f"shared_{name}", ROOT / "scripts" / "shared" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


common = load("common")
stats = load("stats")
conditions = load("conditions")


class TestCommon(unittest.TestCase):
    def test_parse_time(self):
        self.assertEqual(common.parse_time("2026-03-01").isoformat(), "2026-03-01T00:00:00+00:00")
        self.assertEqual(common.parse_time("2026-03-01T10:00:00Z").hour, 10)
        self.assertEqual(common.parse_time("2026-03-01T10:00:00+10:00").hour, 0)
        self.assertIsNone(common.parse_time(""))
        with self.assertRaises(common.InputError):
            common.parse_time("yesterday", "f.csv:2")

    def test_parse_bool(self):
        self.assertTrue(common.parse_bool("Yes"))
        self.assertFalse(common.parse_bool("0"))
        self.assertIsNone(common.parse_bool(""))
        with self.assertRaises(common.InputError):
            common.parse_bool("maybe")


class TestStats(unittest.TestCase):
    def test_wilson_known_value(self):
        lo, hi = stats.wilson(81, 263)       # Newcombe (1998) example: 0.2553 – 0.3662
        self.assertAlmostEqual(lo, 0.2553, places=3)
        self.assertAlmostEqual(hi, 0.3662, places=3)

    def test_newcombe_known_value(self):
        d, lo, hi = stats.newcombe_diff(56, 70, 48, 80)   # Newcombe example: 0.0524 – 0.3339
        self.assertAlmostEqual(d, 0.2, places=6)
        self.assertAlmostEqual(lo, 0.0524, places=3)
        self.assertAlmostEqual(hi, 0.3339, places=3)

    def test_fisher_known_value(self):
        self.assertAlmostEqual(stats.fisher_exact(1, 9, 11, 3), 0.002759, places=5)
        self.assertAlmostEqual(stats.fisher_exact(3, 1, 1, 3), 0.4857, places=3)

    def test_holm(self):
        self.assertEqual([round(x, 4) for x in stats.holm([0.01, 0.04, 0.03])], [0.03, 0.06, 0.06])

    def test_srm(self):
        self.assertGreater(stats.srm_p(5000, 5000, 0.5), 0.99)
        self.assertLess(stats.srm_p(5300, 4700, 0.5), 0.001)

    def test_sample_size(self):
        n_c, n_t = stats.sample_size_per_arm(0.30, 0.35)
        self.assertTrue(1350 <= n_c <= 1400, n_c)     # textbook value ~1374
        self.assertEqual(n_c, n_t)
        self.assertTrue(math.isinf(stats.sample_size_per_arm(0.3, 0.3)[0]))


class TestConditions(unittest.TestCase):
    def ok(self, expr, row):
        fn, _ = conditions.compile_condition(expr)
        return fn(row)

    def test_basic(self):
        self.assertTrue(self.ok("lessons >= 1", {"lessons": "2"}))
        self.assertFalse(self.ok("lessons >= 1", {"lessons": "0"}))
        self.assertTrue(self.ok('plan == "monthly" or plan == "weekly"', {"plan": "weekly"}))

    def test_precedence_and_parens(self):
        row = {"a": "1", "b": "0", "c": "0"}
        self.assertTrue(self.ok("a == 1 or b == 1 and c == 1", row))
        self.assertFalse(self.ok("(a == 1 or b == 1) and c == 1", row))

    def test_missing_is_null(self):
        self.assertFalse(self.ok("lessons >= 0", {"lessons": ""}))
        self.assertFalse(self.ok("lessons != 3", {}))
        self.assertTrue(self.ok("lessons == null", {"lessons": ""}))
        self.assertTrue(self.ok("lessons != null", {"lessons": "0"}))

    def test_bools(self):
        self.assertTrue(self.ok("active == true", {"active": "yes"}))
        self.assertTrue(self.ok("active == 1", {"active": True}))

    def test_fields(self):
        _, fields = conditions.compile_condition("a == 1 and (b > 2 or c == null)")
        self.assertEqual(fields, {"a", "b", "c"})

    def test_rejects_unsafe(self):
        for bad in ["__import__('os')", "a == 1 +", "a ==", "a > \"x\"", "a == 1 or", ""]:
            with self.assertRaises(conditions.ConditionError, msg=bad):
                conditions.compile_condition(bad)


class TestBlocksInSync(unittest.TestCase):
    def test_sync_check(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_shared_blocks.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
