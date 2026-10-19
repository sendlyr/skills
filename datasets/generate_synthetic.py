#!/usr/bin/env python3
"""Generate the synthetic "Practica" example dataset with planted, known answers.

Practica is a fictional language-learning app with a 7-day free trial that converts
to paid automatically. The world is built so that every skill in this repo has a
right answer to find:

- The setup step (``goal_set``) is the cliff: users who never set a goal almost never pay.
  This mirrors Typesy Homeschool, where "parent adds a child" was the real indicator.
- ``lesson_completed`` >= 1 within 3 days is the supporting signal; 3+ lessons is barely
  better than 1 ("nothing vs something", not "a little vs a lot").
- ``email_opened`` is a confounded decoy: motivated users open more email and also
  convert more, but opening email causes nothing.
- ``app_opened`` >= 1 on day 0 is too broad (almost everyone does it).
- ``billing_page_viewed`` mostly happens *after* conversion; it only looks predictive if
  you let post-outcome behaviour leak into the window. About 8% of payers upgrade early,
  inside the trial, so the leakage guard has real work to do.
- ``streak_reminder_shown`` is performed by the system, not the learner, so email cannot
  ask anyone to do it.
- The last two weeks of signups are not mature for a 14-day outcome.
- A good experiment (state-routed emails, 95%+ reach) moves conversion; a broken run of
  the same experiment (an outage, sends to already-active users, cap drift, spacing
  violations, control contamination) cannot be interpreted.

Only ``random.Random.random()`` is used so the output is stable across Python versions.

Usage:
    python3 datasets/generate_synthetic.py --out examples/practica
    python3 datasets/generate_synthetic.py --out examples/practica --check   # verify committed files
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import random

SEED = 20261019
UTC = timezone.utc

OBS_START = datetime(2026, 1, 5, tzinfo=UTC)
OBS_END = datetime(2026, 5, 3, tzinfo=UTC)          # last observational anchor (exclusive)
OBS_AS_OF = datetime(2026, 5, 10, tzinfo=UTC)       # data extracted this day
OBS_ACCOUNTS = 5000

EXP_START = datetime(2026, 5, 11, tzinfo=UTC)
EXP_END = datetime(2026, 6, 22, tzinfo=UTC)         # cohort_end is the day before
EXP_AS_OF = datetime(2026, 7, 15, tzinfo=UTC)
EXP_USERS = 8000
EXP_SALT = "practica-2026q2"
EXP_ALLOCATION = 0.5
OUTAGE_START_DAY = 14                               # broken run: no sends for users assigned
OUTAGE_END_DAY = 27                                 # in [start, end) days after EXP_START

DECISION_WINDOW_DAYS = 7
OUTCOME_WINDOW_DAYS = 14


class Rng:
    """Thin wrapper that only ever calls random() for cross-version stability."""

    def __init__(self, seed: int) -> None:
        self._r = random.Random(seed)

    def u(self, a: float = 0.0, b: float = 1.0) -> float:
        return a + (b - a) * self._r.random()

    def p(self, prob: float) -> bool:
        return self._r.random() < prob

    def geom(self, p_more: float, cap: int) -> int:
        n = 0
        while n < cap and self._r.random() < p_more:
            n += 1
        return n


def hours(x: float) -> timedelta:
    return timedelta(hours=x)


def days(x: float) -> timedelta:
    return timedelta(days=x)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def hash_bucket(salt: str, stratum: str, user_id: str) -> float:
    """Same rule as holdout.py assign: uniform in [0, 1) from sha256."""
    digest = hashlib.sha256(f"{salt}:{stratum}:{user_id}".encode()).hexdigest()
    return int(digest[:13], 16) / 16 ** 13


# ---------------------------------------------------------------------------
# One user's trial
# ---------------------------------------------------------------------------

def simulate_user(rng: Rng, anchor: datetime, *, contact_at: datetime | None = None,
                  nudge_strength: float = 0.0) -> dict:
    """Simulate one trial. ``contact_at`` is when the first state-routed email lands
    (None = never contacted). ``nudge_strength`` scales the causal effect of contact."""
    m = rng.u()                                  # latent motivation (unobserved)
    is_test = rng.p(0.01)
    cancelled = rng.p(0.02)
    events: list[tuple[str, str, datetime]] = []

    # Opening the app: nearly universal on day 0.
    if rng.p(0.975):
        events.append(("app_opened", "learner", anchor + hours(rng.u(0.0, 6.0))))
    for d in range(1, 8):
        if rng.p(0.12 + 0.55 * m):
            events.append(("app_opened", "learner", anchor + days(d) + hours(rng.u(0.0, 20.0))))

    def contacted_before(t: datetime) -> bool:
        return contact_at is not None and contact_at < t

    # Setup step: set a learning goal.
    goal_at = None
    if rng.p(0.42 + 0.36 * m):
        goal_at = anchor + hours(rng.u(0.1, 20.0))
        if rng.p(0.12):
            goal_at = anchor + hours(rng.u(24.0, 70.0))          # late setters
    elif contact_at is not None and contact_at < anchor + hours(72) and rng.p(0.45 * nudge_strength):
        goal_at = contact_at + hours(rng.u(0.5, 30.0))           # the email moved them
    if cancelled and goal_at is not None and rng.p(0.5):
        goal_at = None

    # Lessons.
    lessons: list[datetime] = []
    if goal_at is not None and not cancelled:
        p_first = 0.26 + 0.50 * m
        if contacted_before(anchor + hours(72)):
            p_first += 0.16 * nudge_strength
        if rng.p(clamp(p_first)):
            start = max(goal_at, anchor)
            room = max(0.5, 71.0 - (start - anchor).total_seconds() / 3600)
            first = start + hours(rng.u(0.2, room))
            lessons.append(first)
            extra = rng.geom(0.30 + 0.40 * m, 10)
            for _ in range(extra):
                if rng.p(0.5):
                    lessons.append(first + hours(rng.u(1.0, 50.0)))
                else:
                    lessons.append(first + hours(rng.u(50.0, 13 * 24.0)))
        elif rng.p(0.18):
            lessons.append(anchor + hours(rng.u(73.0, 7 * 24.0)))
    lessons.sort()
    for t in lessons:
        events.append(("lesson_completed", "learner", t))
    if goal_at is not None:
        events.append(("goal_set", "learner", goal_at))

    lessons_3d = sum(1 for t in lessons if t < anchor + hours(72))
    lessons_7d = sum(1 for t in lessons if t < anchor + days(7))

    # The system reacts to activity: not something email can ask a learner to do.
    if lessons_3d >= 1 and rng.p(0.9):
        events.append(("streak_reminder_shown", "system", lessons[0] + hours(rng.u(18.0, 26.0))))

    # Marketing email opens: driven by motivation only (confounded decoy).
    if rng.p(0.18 + 0.62 * m):
        n_opens = 1 + rng.geom(0.25 + 0.45 * m, 6)
        for _ in range(n_opens):
            events.append(("email_opened", "learner", anchor + hours(rng.u(1.0, 70.0))))

    # Outcome: auto-conversion at the end of the 7-day trial.
    if cancelled:
        p_conv = 0.01
    elif goal_at is None:
        p_conv = 0.04
    elif lessons_3d == 0:
        p_conv = 0.30 if lessons_7d > 0 else 0.19
    elif lessons_3d < 3:
        p_conv = 0.50
    else:
        p_conv = 0.53
    p_conv += 0.06 * (m - 0.5)
    converted = rng.p(clamp(p_conv))
    outcome_at = anchor + days(7) + hours(rng.u(0.0, 10.0)) if converted else None
    if converted and rng.p(0.08):
        outcome_at = anchor + hours(rng.u(30.0, 150.0))          # upgraded early, inside the trial

    # Billing page: mostly after paying (leak bait), a little intent beforehand.
    if converted and rng.p(0.85):
        events.append(("billing_page_viewed", "learner", outcome_at + hours(rng.u(0.1, 30.0))))
    if rng.p(0.07 if converted else 0.02):
        events.append(("billing_page_viewed", "learner", anchor + hours(rng.u(110.0, 166.0))))

    app_opens_3d = sum(1 for (name, _, t) in events if name == "app_opened" and t < anchor + hours(72))

    return {
        "anchor": anchor,
        "is_test": is_test,
        "cancelled": cancelled,
        "goal_at": goal_at,
        "lessons": lessons,
        "lessons_3d": lessons_3d,
        "app_opens_3d": app_opens_3d,
        "converted": converted,
        "outcome_at": outcome_at,
        "events": events,
    }


def state_at(user: dict, t: datetime) -> str:
    if any(x < t for x in user["lessons"]):
        return "ACTIVE"
    if user["goal_at"] is not None and user["goal_at"] < t:
        return "GOAL_SET_NO_LESSON"
    return "NO_GOAL"


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def csv_text(header: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def b(x: bool) -> int:
    return 1 if x else 0


# ---------------------------------------------------------------------------
# Observational dataset (for finding-leading-indicators and designing-lifecycle-states)
# ---------------------------------------------------------------------------

def build_observational(rng: Rng) -> tuple[dict[str, str], dict]:
    span = (OBS_END - OBS_START).total_seconds()
    accounts, events, facts = [], [], []
    users = []
    for i in range(OBS_ACCOUNTS):
        anchor = OBS_START + timedelta(seconds=span * i / OBS_ACCOUNTS + rng.u(0, 3600))
        aid = f"acc_{i + 1:05d}"
        u = simulate_user(rng, anchor)
        users.append(u)
        outcome_at = u["outcome_at"]
        if outcome_at is not None and outcome_at > OBS_AS_OF:
            outcome_at = None                                   # not observed yet
        accounts.append([aid, iso(anchor), iso(outcome_at) if outcome_at else "", iso(OBS_AS_OF)])
        for (name, actor, t) in u["events"]:
            if t <= OBS_AS_OF:
                events.append([aid, name, iso(t), actor])
        mature = anchor + days(OUTCOME_WINDOW_DAYS) <= OBS_AS_OF
        lessons_cell = "" if rng.p(0.015) else u["lessons_3d"]    # tracking gap -> UNOBSERVABLE
        facts.append([
            f"usr_{i + 1:05d}", b(u["goal_at"] is not None and u["goal_at"] < anchor + hours(72)),
            lessons_cell, u["app_opens_3d"], b(u["is_test"]), b(u["cancelled"]),
            (b(u["converted"]) if mature else ""),
        ])
    events.sort(key=lambda r: (r[2], r[0], r[1]))
    files = {
        "observational/accounts.csv": csv_text(["account_id", "anchor_at", "outcome_at", "observed_until"], accounts),
        "observational/events.csv": csv_text(["account_id", "event_name", "occurred_at", "actor"], events),
        "observational/facts.csv": csv_text(
            ["user_id", "goal_set", "lessons_completed", "app_opens_3d", "is_test", "cancelled", "converted"], facts),
    }

    mature_users = [u for u in users if u["anchor"] + days(OUTCOME_WINDOW_DAYS) <= OBS_AS_OF]
    truth = {
        "accounts": len(users),
        "mature_accounts": len(mature_users),
        "immature_accounts": len(users) - len(mature_users),
    }
    return files, truth


# ---------------------------------------------------------------------------
# Experiment datasets (for holdout, readout, journeys)
# ---------------------------------------------------------------------------

def build_experiment(seed: int, broken: bool) -> tuple[dict[str, str], dict]:
    rng = Rng(seed)
    span = (EXP_END - EXP_START).total_seconds()
    assignments, outcomes, sends = [], [], []
    n_treat = n_ctrl = 0
    for i in range(EXP_USERS):
        uid = f"u_{i + 1:05d}"
        assigned_at = EXP_START + timedelta(seconds=span * i / EXP_USERS + rng.u(0, 3600))
        arm = "treatment" if hash_bucket(EXP_SALT, "", uid) < EXP_ALLOCATION else "control"
        in_outage = OUTAGE_START_DAY <= (assigned_at - EXP_START).days < OUTAGE_END_DAY

        # Decide contact before simulating, because contact changes behaviour.
        contact_at = None
        strength = 0.0
        if arm == "treatment":
            if not broken:
                if rng.p(0.97):
                    contact_at = assigned_at + hours(rng.u(2.0, 30.0))
                strength = 1.0
            else:
                if not in_outage and rng.p(0.95):
                    contact_at = assigned_at + hours(rng.u(2.0, 60.0))
                strength = 0.45                                  # generic, mistargeted messages
        user = simulate_user(rng, assigned_at, contact_at=contact_at, nudge_strength=strength)

        eligible = not (user["is_test"] or user["cancelled"])
        reason = "" if eligible else ("test_account" if user["is_test"] else "cancelled_before_assignment")
        if arm == "treatment":
            n_treat += 1
        else:
            n_ctrl += 1
        assignments.append([uid, arm, iso(assigned_at), b(eligible), reason])

        lesson_done_3d = b(user["lessons_3d"] >= 1)
        converted = b(user["converted"])
        if rng.p(0.01):                                          # tracking gap: unmeasured
            converted_cell, mech_cell = "", ""
        else:
            converted_cell, mech_cell = converted, lesson_done_3d
        outcomes.append([uid, converted_cell, mech_cell])

        if arm == "treatment" and eligible and contact_at is not None:
            sends.extend(treatment_sends(rng, uid, user, contact_at, broken))
        if arm == "control" and broken and rng.p(12 / 3500):     # control contamination
            t = assigned_at + hours(rng.u(4.0, 40.0))
            sends.append([uid, iso(t), "sent", state_at(user, t), "nudge_generic", iso(t - hours(1))])

    sends.sort(key=lambda r: (r[1], r[0]))
    folder = "experiment-broken" if broken else "experiment"
    files = {
        f"{folder}/assignments.csv": csv_text(["user_id", "arm", "assigned_at", "eligible", "exclusion_reason"], assignments),
        f"{folder}/outcomes.csv": csv_text(["user_id", "converted", "lesson_done_3d"], outcomes),
        f"{folder}/sends.csv": csv_text(["user_id", "sent_at", "status", "state_at_send", "message_key", "rendered_at"], sends),
    }
    return files, {"treatment": n_treat, "control": n_ctrl}


def treatment_sends(rng: Rng, uid: str, user: dict, contact_at: datetime, broken: bool) -> list[list]:
    rows = []
    anchor = user["anchor"]
    if not broken:
        # Good policy: one email per non-success state, max 3, >= 48h apart, stop on success.
        t = contact_at
        sent_states: set[str] = set()
        n = 0
        while n < 3 and t < anchor + days(6):
            st = state_at(user, t)
            if st == "ACTIVE":
                rows.append([uid, iso(t), "not_needed", st, "", ""])
                break
            if st not in sent_states:
                status = "sent"
                r = rng.u()
                if r < 0.015:
                    status = "suppressed"
                elif r < 0.025:
                    status = "failed"
                key = "pick_goal" if st == "NO_GOAL" else "first_lesson"
                rows.append([uid, iso(t), status, st, key, iso(t - hours(rng.u(0.0, 0.2)))])
                if status == "sent":
                    sent_states.add(st)
                    n += 1
            t = t + hours(48)
        return rows
    # Broken policy (the Typesy Homeschool pattern): stuck users get one generic email and
    # then fall out of the journey, while already-active users keep getting "keep going"
    # emails every day. The cap drifted to 5, retries land inside 24h, and content is
    # rendered at queue time and sent later.
    t = contact_at
    n = 0
    stuck_sent = False
    while n < 5 and t < anchor + days(7):
        st = state_at(user, t)
        if st != "ACTIVE" and stuck_sent:
            t = t + hours(rng.u(22.0, 30.0))
            continue
        rendered = t - hours(rng.u(1.0, 40.0))
        key = "keep_going" if st == "ACTIVE" else "nudge_generic"
        rows.append([uid, iso(t), "sent", st, key, iso(rendered)])
        n += 1
        if st != "ACTIVE":
            stuck_sent = True
        if rng.p(0.12) and n < 5:                                 # duplicate retry 1-3h later
            t2 = t + hours(rng.u(1.0, 3.0))
            rows.append([uid, iso(t2), "sent", state_at(user, t2), key, iso(rendered)])
            n += 1
        t = t + hours(rng.u(22.0, 30.0))
    return rows


# ---------------------------------------------------------------------------
# Static config and email examples
# ---------------------------------------------------------------------------

PREREG = """\
[experiment]
name = "practica-trial-activation-2026q2"
hypothesis = "Routing day-0 to day-6 emails by activation state raises 14-day paid conversion."
mechanism = "More trial users set a goal and finish a first lesson within 3 days."
unit = "user"
allocation_treatment = 0.5
salt = "practica-2026q2"
cohort_start = "2026-05-11"
cohort_end = "2026-06-21"
analysis_not_before = "2026-07-06"

[primary]
metric = "converted"
baseline_rate = 0.23
minimum_worthwhile_effect = 0.03
direction = "increase"
confidence_level = 0.95

[mechanism]
metric = "lesson_done_3d"

[gates]
treatment_reach_min = 0.90
first_contact_sla_hours = 48
max_missing_outcome_share = 0.05
srm_p_min = 0.001
control_contact_allowed = false

[policy]
treatment = "state-routed emails per states/states.toml and contact-policy.toml"
control = "existing day-based welcome drip (unchanged)"
"""

CONTACT_POLICY = """\
[policy]
max_sends_per_user = 3
min_hours_between_sends = 24
first_contact_sla_hours = 48
treatment_reach_min = 0.90
control_contact_allowed = false

[states]
success = ["ACTIVE"]
no_send = ["ACTIVE", "EXCLUDED", "UNOBSERVABLE"]
"""

STATES_GOOD = """\
# A small, honest state model for Practica's 7-day trial.
# One state = one ask by the person who reads the email. Success does not send.

[model]
name = "practica_trial_activation_v2"
email_actor = "learner"
decision_window_days = 7

[unobservable]
required_fields = ["goal_set", "lessons_completed"]

[[exclusions]]
name = "EXCLUDED"
when = "is_test == 1 or cancelled == 1"
reason = "test_or_cancelled"

[[states]]
name = "ACTIVE"
when = "lessons_completed >= 1"
success = true
send = false
ask = ""

[[states]]
name = "GOAL_SET_NO_LESSON"
when = "goal_set == 1 and lessons_completed == 0"
send = true
ask = "Finish your first 5-minute lesson"
actor = "learner"

[[states]]
name = "NO_GOAL"
when = "goal_set == 0"
send = true
ask = "Pick your learning goal"
actor = "learner"

[fallback]
name = "UNCLASSIFIED"
"""

STATES_FLAWED = """\
# The kind of state model teams usually start with. It has five planted problems:
# 1. AT_RISK is checked before the setup states, so it swallows users who never set a goal
#    and tells them to "pick up where you left off" (wrong premise).
# 2. NEW can never match: AT_RISK already captured every user with zero app opens.
# 3. LEARNING and STREAKING make the same ask.
# 4. LEARNING and STREAKING do not differ on conversion: lesson depth does not earn a state.
# 5. STREAKING is the success state but still sends.

[model]
name = "practica_trial_v1_legacy"
email_actor = "learner"
decision_window_days = 7

[[exclusions]]
name = "EXCLUDED"
when = "is_test == 1 or cancelled == 1"
reason = "test_or_cancelled"

[[states]]
name = "STREAKING"
when = "lessons_completed >= 3"
success = true
send = true
ask = "Keep your streak going"
actor = "learner"

[[states]]
name = "LEARNING"
when = "lessons_completed >= 1"
send = true
ask = "Keep your streak going"
actor = "learner"

[[states]]
name = "AT_RISK"
when = "app_opens_3d <= 1"
send = true
ask = "Pick up where you left off"
actor = "learner"

[[states]]
name = "NEW"
when = "goal_set == 0 and app_opens_3d == 0"
send = true
ask = "Welcome to Practica"
actor = "learner"

[[states]]
name = "GOAL_SET_NO_LESSON"
when = "goal_set == 1 and lessons_completed == 0"
send = true
ask = "Finish your first 5-minute lesson"
actor = "learner"

[[states]]
name = "NO_GOAL"
when = "goal_set == 0"
send = true
ask = "Pick your learning goal"
actor = "learner"

[fallback]
name = "UNCLASSIFIED"
"""

CLAIM_RULES = """\
[product]
name = "Practica"
forbidden_names = ["Practica Pro", "PRX"]

[[cta]]
key = "pick_goal"
label = "Pick your goal"
url = "https://app.practica.example/goal"

[[cta]]
key = "first_lesson"
label = "Start your first lesson"
url = "https://app.practica.example/lesson/first"

[[prohibited]]
phrases = ["guaranteed", "fluent in 7 days", "100% free forever"]
level = "blocker"
reason = "unsupported outcome claim"

[[prohibited]]
phrases = ["last chance", "act now", "lose your progress"]
level = "warning"
reason = "urgency or loss pressure"

[[prohibited]]
phrases = ["upgrade now", "buy now", "checkout"]
level = "blocker"
reason = "purchase pressure: the trial converts automatically"

[[patterns]]
regex = "\\\\b\\\\d+\\\\s*(seconds|minutes|mins)\\\\b"
level = "blocker"
reason = "exact usage metric in copy"

[[patterns]]
regex = "\\\\bday\\\\s+\\\\d+\\\\b"
level = "warning"
reason = "exact trial day in copy"

[[fact_rules]]
when = "lessons_completed == 0"
forbid = ["you completed", "you finished", "your first lesson is done", "great progress"]
level = "blocker"
reason = "claims progress without evidence"

[[fact_rules]]
when = "goal_set == 0"
forbid = ["your goal is set", "the goal you set", "your goal of"]
level = "blocker"
reason = "assumes a goal that does not exist"

[greeting]
verified_name_field = "first_name"
fallback = "Hi there,"

[required]
footer = true
unsubscribe_token = "{{ unsubscribe_url }}"

[template]
allowed_placeholders = ["first_name", "lessons_completed", "cta_url", "unsubscribe_url"]
"""


def email(subject, intro, body, cta_label, cta_url, footer="You're receiving this because you started a Practica trial. Unsubscribe: {{ unsubscribe_url }}",
          preheader="", headline=""):
    return {"subject": subject, "preheader": preheader, "headline": headline, "intro": intro,
            "body": body, "cta_label": cta_label, "cta_url": cta_url, "footer": footer}


GOAL_URL = "https://app.practica.example/goal"
LESSON_URL = "https://app.practica.example/lesson/first"

EMAILS = {
    "emails": [
        {"id": "e01_clean_no_goal", "state": "NO_GOAL",
         "facts": {"first_name": "Ana", "goal_set": 0, "lessons_completed": 0},
         "email": email("One choice to make your trial count", "Hi Ana,",
                        ["Practica works best when it knows what you're learning for.",
                         "Pick a goal and we'll shape your first lesson around it."],
                        "Pick your goal", GOAL_URL)},
        {"id": "e02_clean_fallback_greeting", "state": "GOAL_SET_NO_LESSON",
         "facts": {"first_name": "", "goal_set": 1, "lessons_completed": 0},
         "email": email("Your first lesson is ready", "Hi there,",
                        ["Your goal is set. The first lesson takes about five minutes.",
                         "Start it now while it's fresh."],
                        "Start your first lesson", LESSON_URL)},
        {"id": "e03_false_completion", "state": "GOAL_SET_NO_LESSON",
         "facts": {"first_name": "Ben", "goal_set": 1, "lessons_completed": 0},
         "email": email("Nice work, Ben", "Hi Ben,",
                        ["You completed your first lesson. Great progress!"],
                        "Start your first lesson", LESSON_URL)},
        {"id": "e04_cta_not_allowed", "state": "NO_GOAL",
         "facts": {"first_name": "Chloe", "goal_set": 0, "lessons_completed": 0},
         "email": email("Let's get you started", "Hi Chloe,",
                        ["Pick what you want to learn."],
                        "Explore plans", "https://practica.example/pricing")},
        {"id": "e05_unsupported_claims", "state": "NO_GOAL",
         "facts": {"first_name": "Dev", "goal_set": 0, "lessons_completed": 0},
         "email": email("Fluent in 7 days, guaranteed", "Hi Dev,",
                        ["Practica gets you fluent in 7 days. Results guaranteed."],
                        "Pick your goal", GOAL_URL)},
        {"id": "e06_exact_metric", "state": "GOAL_SET_NO_LESSON",
         "facts": {"first_name": "Eli", "goal_set": 1, "lessons_completed": 0},
         "email": email("You're close", "Hi Eli,",
                        ["You spent 23 minutes exploring yesterday. Your first lesson is next."],
                        "Start your first lesson", LESSON_URL)},
        {"id": "e07_unverified_greeting", "state": "NO_GOAL",
         "facts": {"first_name": "", "goal_set": 0, "lessons_completed": 0},
         "email": email("Pick your goal", "Hi fkim88,",
                        ["Practica works best with a goal."],
                        "Pick your goal", GOAL_URL)},
        {"id": "e08_internal_name_no_unsubscribe", "state": "NO_GOAL",
         "facts": {"first_name": "Gia", "goal_set": 0, "lessons_completed": 0},
         "email": email("Welcome to Practica Pro", "Hi Gia,",
                        ["Practica Pro is ready for you."],
                        "Pick your goal", GOAL_URL, footer="Thanks for trying Practica.")},
        {"id": "e09_urgency_warning", "state": "GOAL_SET_NO_LESSON",
         "facts": {"first_name": "Hal", "goal_set": 1, "lessons_completed": 0},
         "email": email("Last chance to start strong", "Hi Hal,",
                        ["Your goal is set. Don't lose your progress: start your first lesson."],
                        "Start your first lesson", LESSON_URL)},
    ]
}

TEMPLATE = {
    "template": {
        "state": "GOAL_SET_NO_LESSON",
        "email": email("Your first lesson is ready, {{ first_name }}", "Hi {{ first_name }},",
                       ["Ivy and other learners finish lesson one in their first day.",
                        "You're on a {{ streak_days }}-day streak. Keep it going."],
                       "Start your first lesson", "{{ cta_url }}"),
    },
    "renders": [
        {"id": "r1", "facts": {"first_name": "Ivy", "goal_set": 1, "lessons_completed": 0},
         "email": email("Your first lesson is ready, Ivy", "Hi Ivy,",
                        ["Ivy and other learners finish lesson one in their first day.",
                         "You're on a 0-day streak. Keep it going."],
                        "Start your first lesson", LESSON_URL)},
        {"id": "r2", "facts": {"first_name": "Jon", "goal_set": 1, "lessons_completed": 0},
         "email": email("Your first lesson is ready, Jon", "Hi Jon,",
                        ["Ivy and other learners finish lesson one in their first day.",
                         "You're on a 0-day streak. Keep it going."],
                        "Start your first lesson", LESSON_URL)},
    ],
}


def lock_for(text: str, name: str, sealed_at: str) -> str:
    digest = hashlib.sha256(text.replace("\r\n", "\n").encode()).hexdigest()
    return json.dumps({"file": name, "sha256": digest, "sealed_at": sealed_at}, indent=2) + "\n"


ANSWER_KEY = {
    "schema_version": 1,
    "about": "Planted truths in the synthetic Practica dataset. Tests and evals assert against this file.",
    "finding-leading-indicators": {
        "args": {"outcome_window_days": OUTCOME_WINDOW_DAYS, "decision_window_days": DECISION_WINDOW_DAYS,
                 "email_actor": "learner", "as_of": "2026-05-10"},
        "top_event": "goal_set",
        "top_threshold": 1,
        "top_window_days_max": 3,
        "supporting_event": "lesson_completed",
        "nothing_vs_something": {"event": "lesson_completed", "threshold_low": 1, "threshold_high": 3,
                                 "note": "conversion if hit barely moves from >=1 to >=3"},
        "must_not_rank_top3": ["billing_page_viewed", "app_opened", "streak_reminder_shown"],
        "too_broad": {"event": "app_opened", "threshold": 1, "window_days": 1},
        "not_actionable_actor": "streak_reminder_shown",
        "confounded_decoy": "email_opened",
        "leak_bait": "billing_page_viewed",
        "immature_accounts_expected": True,
        "windows_beyond_decision_window_refused": 14,
    },
    "designing-lifecycle-states": {
        "good_model": "states/states.toml",
        "flawed_model": "states/states.flawed.toml",
        "flawed_findings": {
            "unreachable_states": ["NEW"],
            "duplicate_asks": [["STREAKING", "LEARNING"]],
            "success_state_sends": ["STREAKING"],
            "indistinguishable_pairs": [["STREAKING", "LEARNING"]],
        },
        "good_findings": {"success_state_sends": [], "unreachable_states": [], "duplicate_asks": []},
        "unobservable_expected": True,
    },
    "designing-holdout-experiments": {
        "salt": EXP_SALT,
        "allocation_treatment": EXP_ALLOCATION,
        "prereg_sealed": "experiment/prereg.toml",
    },
    "writing-decision-readouts": {
        "experiment": {"verdict": "SUPPORTED_AT_TARGET"},
        "experiment-broken": {"verdict": "INVALID_DELIVERY",
                              "failed_gates_include": ["treatment_reach", "control_contacted"]},
        "per_protocol_must_not_appear": True,
    },
    "designing-state-journeys": {
        "experiment": {"reach_gate": "pass", "success_state_send_share_max": 0.05,
                       "cap_violations": 0, "spacing_violations": 0, "control_contacted": 0},
        "experiment-broken": {"reach_gate": "fail", "success_state_send_share_min": 0.40,
                              "cap_violations_min": 1, "spacing_violations_min": 1, "control_contacted_min": 1,
                              "stale_render_hours_p50_min": 1.0},
    },
    "grounding-lifecycle-emails": {
        "clean": ["e01_clean_no_goal", "e02_clean_fallback_greeting"],
        "blockers": {
            "e03_false_completion": ["fact_rule"],
            "e04_cta_not_allowed": ["cta"],
            "e05_unsupported_claims": ["prohibited"],
            "e06_exact_metric": ["pattern"],
            "e07_unverified_greeting": ["greeting"],
            "e08_internal_name_no_unsubscribe": ["product_name", "required"],
        },
        "warnings_only": {"e09_urgency_warning": ["prohibited"]},
        "template_blockers": ["unknown_placeholder", "literal_name_in_template", "cross_user_name"],
    },
}


def build_all() -> dict[str, str]:
    files: dict[str, str] = {}
    obs_files, obs_truth = build_observational(Rng(SEED))
    files.update(obs_files)
    good_files, good_counts = build_experiment(SEED + 1, broken=False)
    files.update(good_files)
    broken_files, _ = build_experiment(SEED + 1, broken=True)
    files.update(broken_files)

    files["states/states.toml"] = STATES_GOOD
    files["states/states.flawed.toml"] = STATES_FLAWED
    for folder in ("experiment", "experiment-broken"):
        files[f"{folder}/prereg.toml"] = PREREG
        files[f"{folder}/prereg.lock"] = lock_for(PREREG, "prereg.toml", "2026-05-08T09:00:00Z")
        files[f"{folder}/contact-policy.toml"] = CONTACT_POLICY
    files["emails/claim-rules.toml"] = CLAIM_RULES
    files["emails/emails.json"] = json.dumps(EMAILS, indent=2) + "\n"
    files["emails/template.json"] = json.dumps(TEMPLATE, indent=2) + "\n"

    key = json.loads(json.dumps(ANSWER_KEY))
    key["observational_counts"] = obs_truth
    key["experiment_counts"] = good_counts
    files["answer_key.json"] = json.dumps(key, indent=2) + "\n"
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default="examples/practica", help="output directory")
    ap.add_argument("--check", action="store_true", help="verify the files on disk match; write nothing")
    args = ap.parse_args(argv)
    out = Path(args.out)
    files = build_all()
    if args.check:
        stale = [name for name, text in files.items()
                 if not (out / name).exists() or (out / name).read_text(encoding="utf-8") != text]
        if stale:
            print("Generated data is out of date. Run: python3 datasets/generate_synthetic.py --out "
                  f"{args.out}\n  " + "\n  ".join(stale), file=sys.stderr)
            return 1
        print(f"OK: {len(files)} files match.")
        return 0
    for name, text in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"Wrote {len(files)} files to {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
