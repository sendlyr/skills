# Pre-registration, field by field

A pre-registration is the list of decisions you are not allowed to make after seeing the data. A timestamp without immutable contents is not a pre-registration. That's why the file is hashed.

| Field | Why it exists |
|---|---|
| `hypothesis` | States a falsifiable claim about the primary outcome |
| `mechanism` | Names the behaviour that should carry the effect, so the readout can tell "the behaviour moved but the outcome didn't" from "nothing moved" |
| `unit` | The randomised unit is the causal unit. Message-level effects can't be identified when users receive several messages |
| `allocation_treatment`, `salt` | Fixed allocation, reproducible assignment. Changing allocation mid-cycle invalidates the comparison |
| `cohort_start`, `cohort_end` | The assignment window. It must start after the shakedown week |
| `analysis_not_before` | The later of: cohort close + outcome window + ingestion grace. Before this date there is no verdict |
| `primary.metric` | Exactly one. Secondary outcomes are reported but cannot rewrite the primary verdict |
| `baseline_rate` | Sizes the experiment. Take it from the eligible population, not the whole user base |
| `minimum_worthwhile_effect` (δ) | The smallest absolute lift that justifies the program. It makes "no worthwhile effect" a possible answer. Without it, a tiny positive estimate gets called a win |
| `direction` | Increase (conversion) or decrease (churn) |
| `confidence_level` | Usually 0.95 |
| `mechanism.metric` | Usually the leading indicator as a 1/0 column |
| `gates.*` | The validity conditions. Failing any of them means the readout refuses to learn |
| `policy.*` | Exactly what treatment and control were, pinned by file hashes |

## The decision rule is fixed in advance

With the confidence interval of treatment − control and δ (checked in order):

1. A gate failed → `INVALID_*`, and no effect is classified.
2. Not mature → `NOT_READY`.
3. Lower bound ≥ δ → `SUPPORTED_AT_TARGET`.
4. Upper bound < 0 → `HARMFUL`.
5. Upper bound < δ → `FALSIFIED_AS_WORTHWHILE`: the data rule out the promised lift.
6. Otherwise → `INCONCLUSIVE`.

Nobody can relabel `INCONCLUSIVE` as `SUPPORTED`. The human decides the *action* (adopt, repeat, revise, stop); the evidence class is not up for discussion.

## What changes require a new cycle

Any change to population, allocation, states, timing, caps, content, primary metric, δ or dates. Write a new hypothesis version that states what changed and why, then seal a new file. A repaired rerun of an *invalid* cycle (e.g. a delivery outage) may reuse the same hypothesis, because it was never tested.

## Shakedown week

Run the treatment pipeline for one week on users who won't be counted. Open the measured cohort only when the week shows:

- timely treatment reach ≥ 90% within the SLA;
- no assignment-without-treatment-send gaps;
- fresh data;
- every non-contact explained by a reason code.

Typesy's restart plan required this after two experiments turned out to have treated only part of their treatment arm.
