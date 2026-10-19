# Refusing to learn: the gates and the traps they catch

> *"Neither experiment failed to show an effect. Neither was ever in a condition to measure one."*
> Sendlyr, reviewing two Typesy experiments, August 2026

## The common root cause

**Nothing in the system measured whether the treatment arm actually received the treatment.** The readouts reported sends. They never reported reach. Under-delivery went unnoticed for months in two experiments.

## Gates

| Gate | Fails when | Trap it catches |
|---|---|---|
| `srm` | Arm sizes differ from the sealed allocation (chi-square p < 0.001) | Broken randomisation, users dropped from one arm, duplicate rows |
| `treatment_reach` | Fewer than 90% of eligible treatment users were contacted (or correctly not needed) within the SLA | An outage, a queueing bug, users who were never visible to the pipeline |
| `control_contacted` | A control user got a treatment message | Leaky suppression, a wrong segment, manual sends |
| `prereg_hash` | `prereg.toml` changed after sealing | Changing the question after seeing the answer |
| `missing_outcomes` | Too many blank primary outcomes | Tracking gaps, immature cohorts, broken joins |
| `maturity` | Before `analysis_not_before` | Peeking and stopping early |

## Typesy's real failures, and what each teaches

1. **Reach.** Homeschool's treatment arm: 534 of 986 assigned users got an email (54.16%). A second look found 333 excluded by design, and against the 665 eligible, reach was **80.30%**. VIP: 189 of 269 (70.26%). Both are below 90%. An effect diluted across an arm that was a fifth to half untreated reads as nothing.
2. **The wrong denominator, twice.** First, 54% was against all assigned users, which overstated the failure. Then a separate 88% indicator rate turned out to count only parents who had logged in; over every assigned user it was 58.55%. Always print the denominator rule next to the rate.
3. **Per-protocol.** "Contacted treatment converted at 67.42% vs control 47.72%." Being contacted selects for users with a snapshot, a valid email, a sendable state and a mature window. Selection alone can produce that gap.
4. **Default-false outcomes.** Outcome booleans defaulted to `false`, so unmeasured users were stored as non-converters. That biases every rate downward.
5. **"Active" didn't mean what it said.** A query filtered snapshots on `is_active = true`, which meant "in the latest import". It made 257 users look like they had never been seen. They all had been.
6. **An unverified control route.** Whether VIP's control received the legacy emails at all couldn't be answered from the database. Without that, the comparison might be emails versus silence.

## What to do after a refusal

1. Run `audit_sends.py` (`designing-state-journeys`) to locate where delivery failed.
2. Fix the pipeline. Run a shakedown week to the gate.
3. Repeat **the same hypothesis version**. It was never tested, so this isn't a revision.
4. Keep the invalid readout on file and label it invalid. Never retrofit it as evidence.
