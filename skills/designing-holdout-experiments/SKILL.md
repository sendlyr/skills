---
name: designing-holdout-experiments
description: Pre-register and set up a randomised holdout that tests whether driving a leading indicator (or a whole lifecycle email policy) actually changes the business outcome. Covers sample size from a pre-set minimum worthwhile effect, deterministic hash assignment, strata, a shakedown week, a treatment-reach gate, and sealing the plan with a hash so the question can't change after the answer is seen. Use when planning an onboarding, lifecycle or activation experiment, asking "how many users do we need", "how long should it run", or "how do we prove this email program works". Hands off to writing-decision-readouts.
license: MIT
metadata:
  author: sendlyr
  version: "0.1.0"
---

# Designing holdout experiments

An indicator from `finding-leading-indicators` *predicts* the outcome. This skill sets up the test of whether *driving* it changes the outcome. The unit is the randomised user. The treatment is the **whole sealed policy** (states, timing, caps, content), not one email.

The point of a pre-registration is that the experiment can come back and say **no**: *"Then it is a test. Found afterwards, it is a story."*

## When to use

- Before launching any lifecycle, onboarding or activation program you want to claim works.
- "How many users do we need / how long will it take?"
- When a previous test "showed nothing" and you want a cleaner rerun.

## What you need

- The **hypothesis** and its **mechanism**: "State-routed emails raise 14-day paid conversion *because* more trial users set a goal in 3 days."
- The **primary outcome**, its window and its anchor. Choose one; secondary outcomes can't rewrite the primary verdict.
- The **baseline rate** of the primary outcome in the eligible population.
- The **minimum worthwhile effect (δ)**: the smallest absolute lift that would justify running the program. *This is a business decision, not a statistic.* Without it, nothing can be falsified.
- **Eligible users per week**, the treatment policy, and the control (usually the existing program, not silence).

## Method

1. **Size it from δ, not from hope.**

   ```bash
   python3 scripts/holdout.py size --baseline 0.23 --mde 0.02 --eligible-per-week 300
   ```

   If it needs more than ~6 months, raise δ, widen the population, or test the mechanism metric first. At low volume this is a slow fixed experiment, never a bandit or per-user optimiser; those would optimise noise.
2. **Define the population before randomising**, using only facts known at assignment: plan, signup date, not test, not cancelled. Never filter on anything that happens after assignment, like first login or being contacted.
3. **Assign deterministically**, once, never re-drawn:

   ```bash
   python3 scripts/holdout.py assign --users eligible.csv --salt my-exp-2026q2 --allocation 0.5 \
     [--stratum-column plan] --out assignments.csv
   ```

   Use 50/50 unless you have a reason. Use strata for segments you will report separately (e.g. monthly/yearly).
4. **Control gets a defined route.** Usually that's the existing program, delivered by the same machinery. Write it down and attest weekly that it ran: *"Control route unverified"* means no verdict.
5. **Write `prereg.toml`** from `assets/prereg.toml`:
   - hypothesis, mechanism, population, allocation and salt;
   - cohort open and close dates, and `analysis_not_before` (cohort close + outcome window + ingestion grace);
   - primary and mechanism metrics, baseline, δ, direction;
   - gates: treatment reach ≥ 90% within a first-contact SLA (48h), maximum missing outcomes, SRM threshold, and control contact not allowed;
   - the policy version (hashes of `states.toml`, `contact-policy.toml` and the approved templates).
6. **Run a shakedown week**, treatment only and not counted. Require timely reach ≥ 90%, no assignment-without-send gaps, fresh data, and every non-contact explained. If it fails, fix the pipeline and repeat.
7. **Seal the plan** before the first counted assignment:

   ```bash
   python3 scripts/holdout.py seal prereg.toml      # writes prereg.lock (sha256)
   python3 scripts/holdout.py verify prereg.toml    # any later check
   ```

   Any edit after sealing makes `readout.py` report `PREREGISTRATION_DRIFT`. A changed question needs a new hypothesis version and a new cycle.
8. **During the run:** automate the daily delivery and data checks. Do a weekly 15-minute look at reach, gaps, freshness and maturity, but **do not look at the arm difference** before the analysis date. Copy or timing changes mid-cycle are protocol deviations.
9. **Hand off** to `writing-decision-readouts` once `analysis_not_before` has passed.

## Rules (from what went wrong)

- **Never compare contacted vs uncontacted users.** Being contacted is not random. In Typesy Homeschool, "contacted treatment" converted at 67.42% vs control at 47.72%. That gap is selection, not lift. The only valid comparison is arms as randomised (intent-to-treat).
- **Measure reach, or the test can't answer its question.** Neither Typesy experiment ever measured whether the treatment arm was treated. Homeschool reached 80.3% of eligible treatment users (534/665); VIP reached 70.3% (189/269). Both were below the 90% gate. *"Neither was ever in a condition to measure one."*
- **No early stopping, no reallocating arms, no new copy mid-cycle.** Fixed 50/50, fixed policy, fixed end date.
- **Denominators are pre-registered.** A primary outcome conditioned on a post-assignment event (e.g. "among users who logged in") is descriptive, not causal.
- **Missing outcomes are not negatives.** Pre-register the missing-outcome rule.
- **The mechanism metric is a separate question.** Typesy VIP moved its indicator +11.7pp (p ≈ 0.051) while conversion moved +0.1pp, against a ~77% baseline with little headroom. Measure both; promise only what δ says.

## References

- `references/preregistration.md`: every field and why it exists.
- `references/power-and-volume.md`: sample-size intuition, slow volumes, and why no bandits.
- `references/assignment-and-delivery.md`: hashing, strata, control route, shakedown, the reach gate.
- `assets/prereg.toml`: the template.

## Next

`writing-decision-readouts` reads `prereg.toml`, `assignments.csv`, `outcomes.csv` and `sends.csv`, and returns one evidence class.
