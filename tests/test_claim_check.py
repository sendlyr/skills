"""End-to-end and rule tests for skills/grounding-lifecycle-emails/scripts/claim_check.py."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "grounding-lifecycle-emails" / "scripts" / "claim_check.py"
EXAMPLES = ROOT / "examples" / "practica" / "emails"
KEY = json.loads((ROOT / "examples" / "practica" / "answer_key.json").read_text(encoding="utf-8"))[
    "grounding-lifecycle-emails"]
REMINDER = "This check catches known mistakes. A human still approves every email before it is sent."

RULES = r'''
[product]
name = "Practica"
forbidden_names = ["Practica Pro"]

[[cta]]
key = "pick_goal"
label = "Pick your goal"
url = "https://app.practica.example/goal"

[[cta]]
key = "first_lesson"
label = "Start your first lesson"
url = "https://app.practica.example/lesson/first"

[[prohibited]]
phrases = ["guaranteed"]
level = "blocker"
reason = "unsupported outcome claim"

[[prohibited]]
phrases = ["last chance"]
level = "warning"
reason = "urgency"

[[patterns]]
regex = '\b\d+\s*minutes\b'
level = "blocker"
reason = "exact usage metric"

[[fact_rules]]
when = "lessons_completed == 0"
forbid = ["you completed"]
level = "blocker"
reason = "claims completion without evidence"

[[fact_rules]]
when = "goal_set == 0"
forbid = ["your goal"]
level = "blocker"
reason = "assumes a goal"

[greeting]
verified_name_field = "first_name"
fallback = "Hi there,"

[required]
footer = true
unsubscribe_token = "{{ unsubscribe_url }}"

[template]
allowed_placeholders = ["first_name", "lessons_completed", "cta_url", "unsubscribe_url"]
'''

FOOTER = "You started a Practica trial. Unsubscribe: {{ unsubscribe_url }}"


def make_email(**overrides):
    email = {
        "subject": "A quick next step",
        "preheader": "",
        "headline": "",
        "intro": "Hi Ana,",
        "body": ["Practica works best when it knows what you want to learn."],
        "cta_label": "Pick your goal",
        "cta_url": "https://app.practica.example/goal",
        "footer": FOOTER,
    }
    email.update(overrides)
    return email


def make_item(item_id="x1", facts=None, **email_overrides):
    base_facts = {"first_name": "Ana", "goal_set": 1, "lessons_completed": 1}
    base_facts.update(facts or {})
    return {"id": item_id, "state": "TEST", "facts": base_facts, "email": make_email(**email_overrides)}


def run_script(rules_path, emails_path, out_dir, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--rules", str(rules_path), "--emails", str(emails_path),
         "--out", str(out_dir), *extra],
        capture_output=True, text=True)


def families(issues, level=None):
    return {i["family"] for i in issues if level is None or i["level"] == level}


class ClaimCheckCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def check(self, payload, rules=RULES, *extra):
        """Write rules and emails, run the script, return (process, result or None)."""
        rules_path = self.tmp / "claim-rules.toml"
        emails_path = self.tmp / "emails.json"
        out = self.tmp / "out"
        rules_path.write_text(rules, encoding="utf-8")
        emails_path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
        proc = run_script(rules_path, emails_path, out, *extra)
        result_path = out / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
        return proc, result

    def one(self, item, rules=RULES):
        """Check a single rendered email; return its result entry."""
        proc, result = self.check({"emails": [item]}, rules)
        self.assertIn(proc.returncode, (0, 1), proc.stderr)
        return result["results"][item["id"]]


class TestExamples(ClaimCheckCase):
    def run_example(self, name, *extra):
        out = self.tmp / name
        proc = run_script(EXAMPLES / "claim-rules.toml", EXAMPLES / name, out, *extra)
        result = json.loads((out / "result.json").read_text(encoding="utf-8"))
        report = (out / "report.md").read_text(encoding="utf-8")
        return proc, result, report

    def test_emails_answer_key(self):
        proc, result, report = self.run_example("emails.json")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        for key in ("schema_version", "summary", "results"):
            self.assertIn(key, result)
        res = result["results"]
        for email_id in KEY["clean"]:
            self.assertEqual(res[email_id]["issues"], [], email_id)
            self.assertEqual(res[email_id]["severity"], "CLEAN")
            self.assertTrue(res[email_id]["passed"])
        for email_id, expected in KEY["blockers"].items():
            r = res[email_id]
            self.assertEqual(r["severity"], "BLOCKED", email_id)
            self.assertFalse(r["passed"])
            self.assertTrue(set(expected) <= families(r["issues"], "blocker"), (email_id, r["issues"]))
        for email_id, expected in KEY["warnings_only"].items():
            r = res[email_id]
            self.assertEqual(r["severity"], "WARNINGS", email_id)
            self.assertTrue(r["passed"])
            self.assertEqual(families(r["issues"], "blocker"), set(), r["issues"])
            self.assertTrue(set(expected) <= families(r["issues"], "warning"), r["issues"])
        n_emails = len(KEY["clean"]) + len(KEY["blockers"]) + len(KEY["warnings_only"])
        self.assertEqual(result["summary"], {**result["summary"], "emails": n_emails, "clean": 2,
                                             "warnings": 1, "blockers": 6})
        for issue in (i for r in res.values() for i in r["issues"]):
            self.assertEqual({"family", "level", "message"} - issue.keys(), set())
            self.assertIn(issue["level"], ("blocker", "warning"))
        self.assertIn("9 emails: 2 clean, 1 with warnings, 6 blocked", report)
        self.assertIn("| e03_false_completion | GOAL_SET_NO_LESSON | BLOCKED |", report)
        self.assertTrue(report.rstrip().endswith(REMINDER))
        self.assertIn("9 emails: 2 clean, 1 with warnings, 6 blocked", proc.stdout)

    def test_emails_no_fail(self):
        proc, result, _ = self.run_example("emails.json", "--no-fail")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result["summary"]["blockers"], 6)

    def test_template_answer_key(self):
        proc, result, report = self.run_example("template.json")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        template = result["template"]
        self.assertFalse(template["passed"])
        group = families(template["issues"], "blocker")
        for r in result["results"].values():
            group |= families(r["issues"], "blocker")
        self.assertTrue(set(KEY["template_blockers"]) <= group, group)
        self.assertTrue(set(KEY["template_blockers"]) <= set(template["group_blocker_families"]))
        self.assertTrue({"unknown_placeholder", "literal_name_in_template"} <= families(template["issues"]))
        own = {k: [i for i in r["issues"] if not i.get("from_template")] for k, r in result["results"].items()}
        self.assertIn("cross_user_name", families(own["r2"]))     # Jon's email names Ivy
        self.assertNotIn("cross_user_name", families(own["r1"]))  # Ivy's own name is fine in her email
        self.assertIn("streak_days", template["placeholders_used"])
        self.assertTrue(report.rstrip().endswith(REMINDER))

    def test_template_no_fail(self):
        proc, _, _ = self.run_example("template.json", "--no-fail")
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TestPhraseRules(ClaimCheckCase):
    def test_baseline_is_clean(self):
        r = self.one(make_item())
        self.assertEqual(r["issues"], [])
        self.assertEqual(r["severity"], "CLEAN")

    def test_word_boundary(self):
        r = self.one(make_item(body=["This plan is unguaranteed and guaranteedly vague."]))
        self.assertNotIn("prohibited", families(r["issues"]))
        r = self.one(make_item(body=["Results guaranteed."]))
        self.assertIn("prohibited", families(r["issues"], "blocker"))

    def test_case_insensitive(self):
        r = self.one(make_item(subject="GUARANTEED results"))
        self.assertIn("prohibited", families(r["issues"], "blocker"))
        self.assertIn('"GUARANTEED"', r["issues"][0]["message"])
        r = self.one(make_item(subject="Last Chance to start"))
        self.assertEqual(r["severity"], "WARNINGS")
        self.assertEqual(families(r["issues"], "warning"), {"prohibited"})
        r = self.one(make_item(body=["You spent 23 MINUTES here."]))
        self.assertIn("pattern", families(r["issues"], "blocker"))

    def test_product_name_and_required(self):
        r = self.one(make_item(subject="Welcome to practica pro", footer=""))
        self.assertTrue({"product_name", "required"} <= families(r["issues"], "blocker"))
        messages = " ".join(i["message"] for i in r["issues"] if i["family"] == "required")
        self.assertIn("footer is empty", messages)
        self.assertIn("{{ unsubscribe_url }}", messages)
        r = self.one(make_item(footer="Thanks.", body=["Unsubscribe: {{unsubscribe_url}}"]))
        self.assertNotIn("required", families(r["issues"]))


class TestFactRules(ClaimCheckCase):
    def test_fires_only_when_condition_true(self):
        claim = ["You completed your first lesson."]
        r = self.one(make_item(facts={"lessons_completed": 0}, body=claim))
        self.assertIn("fact_rule", families(r["issues"], "blocker"))
        self.assertIn("lessons_completed = 0", r["issues"][0]["message"])
        r = self.one(make_item(facts={"lessons_completed": 2}, body=claim))
        self.assertEqual(r["issues"], [])
        r = self.one(make_item(facts={"lessons_completed": 0}, body=["Your first lesson is ready."]))
        self.assertEqual(r["issues"], [])

    def test_missing_fact_is_a_warning_not_a_match(self):
        r = self.one(make_item(facts={"lessons_completed": ""}, body=["You completed your first lesson."]))
        self.assertEqual(r["severity"], "WARNINGS")
        self.assertEqual(families(r["issues"], "warning"), {"fact_rule"})

    def test_approved_cta_label_is_an_ask_not_a_claim(self):
        r = self.one(make_item(facts={"goal_set": 0}, subject="Pick your goal"))
        self.assertEqual(r["issues"], [])
        r = self.one(make_item(facts={"goal_set": 0}, body=["Your goal is waiting."]))
        self.assertIn("fact_rule", families(r["issues"], "blocker"))


class TestGreeting(ClaimCheckCase):
    def test_blank_name_needs_fallback(self):
        r = self.one(make_item(facts={"first_name": ""}, intro="Hi fkim88,"))
        self.assertEqual(families(r["issues"], "blocker"), {"greeting"})
        self.assertIn("Never guess a name", r["issues"][0]["message"])
        self.assertIn('"Hi fkim88,"', r["issues"][0]["message"])
        r = self.one(make_item(facts={"first_name": ""}, intro="Hi there,"))
        self.assertEqual(r["issues"], [])
        r = self.one(make_item(facts={"first_name": None}, intro="Welcome aboard!"))
        self.assertEqual(families(r["issues"], "blocker"), {"greeting"})
        item = make_item()
        del item["facts"]["first_name"]
        item["email"]["intro"] = "Hello Sam,"
        self.assertEqual(families(self.one(item)["issues"], "blocker"), {"greeting"})

    def test_verified_name_must_match(self):
        r = self.one(make_item(intro="Hi Bob,"))
        self.assertEqual(families(r["issues"], "blocker"), {"greeting"})
        self.assertIn('"Ana"', r["issues"][0]["message"])
        for ok in ("Hi Ana,", "hi ana, welcome back", "Hi there,", "Thanks for starting your trial."):
            self.assertEqual(self.one(make_item(intro=ok))["issues"], [], ok)


class TestCta(ClaimCheckCase):
    def test_known_label_wrong_url(self):
        r = self.one(make_item(cta_url="https://app.practica.example/pricing"))
        self.assertEqual(families(r["issues"], "blocker"), {"cta"})
        msg = r["issues"][0]["message"]
        self.assertIn("https://app.practica.example/goal", msg)
        self.assertIn("Closest allowlisted CTA: pick_goal", msg)

    def test_unknown_cta_reports_closest(self):
        r = self.one(make_item(cta_label="Start a lesson", cta_url="https://app.practica.example/lesson"))
        self.assertEqual(families(r["issues"], "blocker"), {"cta"})
        self.assertEqual(r["issues"][0]["closest"], "first_lesson")


class TestTemplate(ClaimCheckCase):
    def template_payload(self, template_email, renders):
        return {"template": {"state": "TEST", "email": template_email}, "renders": renders}

    def test_single_brace_placeholder(self):
        payload = self.template_payload(make_email(intro="Hi {first_name},", cta_url="{{ cta_url }}"),
                                        [make_item("r1")])
        proc, result = self.check(payload)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        issues = result["template"]["issues"]
        self.assertEqual(families(issues), {"unknown_placeholder"})
        self.assertIn("malformed", issues[0]["message"])

    def test_unknown_and_unsupported_placeholders(self):
        payload = self.template_payload(
            make_email(intro="Hi {{ first_name | upcase }},", body=["{{ streak_days }} days in."],
                       cta_url="{{ cta_url }}"),
            [make_item("r1")])
        _, result = self.check(payload)
        texts = {i["text"] for i in result["template"]["issues"] if i["family"] == "unknown_placeholder"}
        self.assertEqual(texts, {"{{ first_name | upcase }}", "{{ streak_days }}"})

    def test_clean_template(self):
        payload = self.template_payload(
            make_email(intro="Hi {{ first_name }},", cta_url="{{ cta_url }}"),
            [make_item("r1", facts={"first_name": "Ana"}, intro="Hi Ana,"),
             make_item("r2", facts={"first_name": "Ben"}, intro="Hi Ben,")])
        proc, result = self.check(payload)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(result["template"]["passed"])
        self.assertEqual(result["summary"]["clean"], 2)

    def test_literal_value_and_inherited_blockers(self):
        payload = self.template_payload(
            make_email(intro="Hi {{ first_name }},", body=["You have finished 3 lessons."], cta_url="{{ cta_url }}"),
            [make_item("r1", facts={"first_name": "Ana", "lessons_completed": 3}, intro="Hi Ana,"),
             make_item("r2", facts={"first_name": "Ben", "lessons_completed": 5}, intro="Hi Ben,")])
        proc, result = self.check(payload)
        self.assertEqual(proc.returncode, 1)
        issues = result["template"]["issues"]
        self.assertEqual(families(issues), {"literal_value_in_template"})
        self.assertIn("{{ lessons_completed }}", issues[0]["message"])
        for r in result["results"].values():          # every render of a blocked template is blocked
            self.assertEqual(r["severity"], "BLOCKED")
            self.assertTrue(all(i.get("from_template") for i in r["issues"]))

    def test_constant_value_is_not_flagged(self):
        payload = self.template_payload(
            make_email(intro="Hi {{ first_name }},", body=["Lessons take 5 steps."], cta_url="{{ cta_url }}"),
            [make_item("r1", facts={"first_name": "Ana", "lessons_completed": 5}, intro="Hi Ana,"),
             make_item("r2", facts={"first_name": "Ben", "lessons_completed": 5}, intro="Hi Ben,")])
        _, result = self.check(payload)
        self.assertEqual(result["template"]["issues"], [])


class TestMalformedInput(ClaimCheckCase):
    def test_bad_regex_exits_2(self):
        rules = RULES.replace(r"regex = '\b\d+\s*minutes\b'", "regex = '(unclosed'")
        proc, result = self.check({"emails": [make_item()]}, rules)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("[[patterns]] #1", proc.stderr)
        self.assertIn("invalid regex", proc.stderr)
        self.assertIsNone(result)

    def test_bad_condition_exits_2(self):
        rules = RULES.replace('when = "goal_set == 0"', 'when = "goal_set === 0"')
        proc, _ = self.check({"emails": [make_item()]}, rules)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("[[fact_rules]] #2", proc.stderr)
        self.assertIn("assumes a goal", proc.stderr)

    def test_bad_level_exits_2(self):
        rules = RULES.replace('level = "warning"', 'level = "maybe"')
        proc, _ = self.check({"emails": [make_item()]}, rules)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("[[prohibited]] #2", proc.stderr)

    def test_bad_toml_and_json_exit_2(self):
        proc, _ = self.check({"emails": [make_item()]}, RULES + "\n[[cta]\n")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("invalid TOML", proc.stderr)
        proc, _ = self.check('{"emails": [')
        self.assertEqual(proc.returncode, 2)
        self.assertIn("invalid JSON", proc.stderr)
        proc, _ = self.check({"emails": [copy.deepcopy(make_item()), make_item()]})
        self.assertEqual(proc.returncode, 2)
        self.assertIn("duplicate id", proc.stderr)


if __name__ == "__main__":
    unittest.main()
