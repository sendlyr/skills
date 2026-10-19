---
name: finding-leading-indicators
description: Find the early user behavior that predicts conversion or retention (the activation signal, "aha moment" or leading indicator) in your own event data, with leakage, maturity and out-of-time checks built in. Use when someone asks what to track, what their activation metric should be, which onboarding or trial behavior predicts paying, why users don't convert, or wants an event export (CSV, SQL, PostHog, Amplitude, Mixpanel, Segment) analysed to pick one behavior to drive. Produces a ranked indicator card labelled predictive, not causal. Hands off to designing-lifecycle-states.
license: MIT
metadata:
  author: sendlyr
  version: "0.1.0"
---

# Finding leading indicators

Find **one early behavior** that separates users who reach the outcome from users who don't. It must happen early enough to act on, and be done by the person you can actually ask.

This skill finds a *candidate*. Correlation picks the candidate; only a holdout proves that driving it changes the outcome (`designing-holdout-experiments`). Never present the result as causal.

## When to use

- "What should we track?" / "What's our activation metric / aha moment?"
- "Which trial behavior predicts conversion?" / "Why do trials not convert?"
- Before designing onboarding emails, lifecycle states or in-product nudges.

Not for: choosing which message to send (`grounding-lifecycle-emails`), or proving a lift (`writing-decision-readouts`).

## What you need

1. **The outcome and its window.** E.g. "paid within 14 days of trial start". Ask if unknown. Don't guess.
2. **The decision window.** How long until the outcome is decided, e.g. a 7-day trial. A signal that fires after this is useless.
3. **Who reads your messages.** E.g. the learner, the parent, the admin. The indicator must be an action *that person* can take.
4. **Two CSVs** (formats in [`docs/data-contracts.md`](../../docs/data-contracts.md); export recipes in `references/preparing-data.md`):
   - `accounts.csv`: `account_id, anchor_at, outcome_at, observed_until`
   - `events.csv`: `account_id, event_name, occurred_at, actor` (`actor` is optional)

Raw rows stay on the user's machine. The script outputs aggregates only. Never paste raw rows, emails or IDs into a chat, a web search or a report.

## Method

1. **Write down the outcome contract first**, before looking at any behavior: outcome, outcome window, anchor (signup or trial start), decision window, and the email actor. Changing these after seeing results is how false signals are born.
2. **Profile the export.** Check the row counts, the date range, and how many distinct users each event has. Note any event that is really the outcome in disguise (`subscription_started`, `invoice_paid`) and drop it.
3. **Score every candidate** (event × threshold × window) with the script below. It:
   - only counts behavior inside `[anchor, anchor + window)`;
   - drops accounts whose outcome landed inside that window (leakage guard);
   - excludes accounts too young to have a measured outcome (maturity);
   - ranks by **lift × coverage** on the older 70% of accounts, then re-checks the top candidates on the newest 30% (out-of-time holdout);
   - refuses windows longer than the decision window, and flags signals that are too broad (≥ 95% coverage), too rare (< 5%), or performed by someone other than the email reader.
4. **Read the nothing-vs-something table.** Most of the separation is usually between doing *nothing* and doing *something*, not between a little and a lot. If bucket 0 → 1 carries the gap, pick threshold 1. A higher bar mostly measures users who are already engaged.
5. **Pick one primary indicator and at most one supporting signal.** Prefer the *earliest* gate with a big cliff (a setup step) over a downstream engagement count. Check that it is:
   - inside the decision window;
   - done by the email reader;
   - not a composite that restates itself (a score that already includes the threshold you're testing);
   - replicated in the holdout.
6. **Write the indicator card** from `assets/indicator-card.md`. Include the caveats verbatim: predictive not causal, the number of candidates tested, and the exclusions.
7. **Hand off:** to `designing-lifecycle-states` to build states around distance-to-indicator, then `designing-holdout-experiments` to test whether driving it moves the outcome.

## Run the script

Paths are relative to this skill's folder. Python 3.11+, no installs.

```bash
python3 scripts/score_signals.py \
  --accounts accounts.csv --events events.csv \
  --outcome-window-days 14 --decision-window-days 7 \
  --email-actor learner --out signal-report/
```

Useful flags:

- `--windows 1,3,7`
- `--thresholds 1,2,3,5`
- `--holdout-share 0.3`
- `--min-users 30`
- `--as-of 2026-05-10` (set this when the data has a known extraction date)

Run `--help` for the full list. Output: `signal-report/report.md` (show this to the user) and `result.json`.

To try it on the bundled synthetic dataset, run from the repo root:

```bash
python3 skills/finding-leading-indicators/scripts/score_signals.py \
  --accounts examples/practica/observational/accounts.csv \
  --events examples/practica/observational/events.csv \
  --outcome-window-days 14 --decision-window-days 7 --email-actor learner --out /tmp/practica-signals
```

The planted answer is `goal_set` (the setup step). `lesson_completed` is the supporting signal. `email_opened` is a confounded decoy, `billing_page_viewed` is leak bait, and `streak_reminder_shown` is done by the system.

## How to explain the result

- Lead with the behavior in plain words, e.g. (Practica example) "Users who set a goal in their first 3 days paid at 36%; those who didn't paid at 3%."
- Give coverage: "60% of trials do it." Low coverage with huge lift is a niche; very high coverage is a non-signal.
- Say "predicts", never "drives" or "causes". Then say how to find out: a holdout.
- Report what was excluded (immature accounts, outcome-in-window accounts) and how many candidates were tried.

## Gotchas (each one cost real time on a real product)

- **The indicator must fire inside the decision window.** Typesy Homeschool's original indicator, "3 pets hatched within 14 days", was used for a 7-day trial. More than half its window fell after the payment decision. Re-scored inside 7 days, it **ranked fifth of seven**.
- **It must be done by the person you email.** In Typesy Homeschool the parent reads the email and the child uses the app. Every "good" candidate was a child behavior. The real cliff was a parent action, *adding a child*: households that never added one converted at **4.0% (6/149)**, against **46.8% (72/154)** once they had. As an indicator, "parent adds a child within 7 days" scored lift × coverage ≈ **47.3**, against **9.4** for the old one.
- **Nothing vs something.** Tightening Typesy's pet threshold barely moved conversion-if-hit (56.2% → 58.7%), while conversion-if-miss climbed (34.2% → 44.7%). The discriminating power sat at the bottom of the range.
- **Composite scores can be circular.** Typesy's `parent_engagement_score` added a bonus when pets ≥ 3. It restated the old indicator inside itself, and contained no parent action despite its name.
- **Denominators lie.** A Homeschool hit rate was reported as **88%**. It only counted parents who had logged in. Over every assigned user it was **58.55% (808/1,380)**. Always state who is in the denominator.
- **Blank is not "no".** An outcome stored as `false` by default makes every unmeasured user look like a non-converter. Keep unmeasured separate.
- **Thresholds tuned on the same data overfit.** Choose round thresholds, confirm on the time holdout, and pre-register before any experiment.
- **It is still correlation.** In Typesy VIP's randomised control arm, users who hit the chosen indicator converted at 75.5% (n = 49) against 78.4% (n = 37) for those who didn't. A behavior picked because it correlated did not predict conversion once randomised. Only a holdout settles it.

## References

- `references/metrics.md`: every metric, flag and readiness rule, and why.
- `references/preparing-data.md`: export recipes (SQL, PostHog, Amplitude, Mixpanel, Segment) and a pre-flight checklist.
- `references/typesy-example.md`: the full Typesy Homeschool indicator story with real numbers.
- `assets/indicator-card.md`: the output template.

## Next

`designing-lifecycle-states` turns the indicator into a small state model. Then `designing-holdout-experiments` tests whether driving the indicator changes the outcome.
