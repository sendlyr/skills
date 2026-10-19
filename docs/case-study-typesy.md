# Case study: Typesy (eReflect), 2026

Published with eReflect's permission. All figures are from production data in 2026.

## Context

Typesy is eReflect's typing-education product. Two trial products, both 7 days and both converting to paid automatically:

- **Typesy VIP:** for individuals.
- **Typesy Homeschool:** the parent signs up and manages child accounts; the children use the product.

Sendlyr's job: find the early behaviour that predicts paying, route onboarding email by each user's distance from it, and measure the result with a randomised holdout.

## VIP: the behaviour moved, conversion didn't

- **Indicator:** complete at least one course within the first 4 days.
- **Design:** treatment got state-routed emails; control got none from Sendlyr.

| | Treatment | Control | Difference (95% CI) |
|---|---:|---:|---:|
| Indicator | 69.4% (129/186) | 57.7% (56/97) | +11.6pp (−0.0 to +23.3), p = 0.051 |
| Trial conversion | 76.8% (136/177) | 76.7% (66/86) | +0.1pp (−10.1 to +11.5) |

**Reading:**

- The emails plausibly moved the behaviour (borderline).
- They didn't move conversion. The leading explanation is a ceiling: about 77% of control trials converted anyway.
- In the control arm, indicator hitters converted at 75.5% (n = 49) vs 78.4% (n = 37). The behaviour wasn't a reliable predictor once randomised.
- Treatment reach was 70.3% (189/269), below the 90% gate the method now requires. Under the method's own rules, this readout is `INVALID_DELIVERY`.

## Homeschool: the routing worked, the targeting didn't

- **Headline:** treatment 58.62% vs control 58.38% on the indicator, a 0.24pp difference: nothing.
- **Delivery:** 80.30% of eligible treatment households reached (534/665).
- **Where the 848 sends went:** 73% to households already past the key action. The 149 households stuck before it (converting at 4.0%) got 116 sends.
- **The real indicator:** the parent adding a child within 7 days. Lift × coverage 47.3, against 9.4 for the original "3 pets in 14 days".
- **Policy drift:** cap 3 → 5 in code; the 24-hour spacing value was never read.

## What changed

The Homeschool restart was designed with:

- three states, with the success state no-send;
- the add-child step as the registered mechanism;
- a fixed 50/50 split, stratified by billing cadence;
- a sealed pre-registration with a minimum worthwhile effect;
- a one-week shakedown gated on ≥ 90% timely reach;
- human batch release, with caps and spacing enforced in the send;
- re-rendering at send time and defined termination reasons.

Every one of those is now a skill in this repo.

## Why publish a null

*"We moved the behaviour. Conversion did not move."* It's the most credible thing a measurement method can show: it can say no, and it can say "we didn't measure that properly".

See [`lessons.md`](lessons.md) for the full list of lessons.
