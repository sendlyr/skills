# Lessons from running this for real

Sendlyr ran this method with eReflect's **Typesy** typing-education products in 2026. Customer 0 had two experiments:

- **Typesy VIP:** a 7-day trial for individuals.
- **Typesy Homeschool:** a 7-day family trial, where the parent signs up and the children do the lessons.

Both trials convert to paid automatically. These are the real numbers, published with permission. Most of them come from the review that asked why neither experiment showed an improvement. The answer:

> **"Neither experiment failed to show an effect. Neither was ever in a condition to measure one."**

---

## 1. Nobody measured reach

The readouts reported sends. They never reported whether the treatment arm was actually treated.

- **Homeschool:** 534 of 986 assigned treatment households got an email (54.16%). 333 were excluded by design; against the 665 eligible, reach was **80.30%**.
- **VIP:** 189 of 269 (70.26%).

Both were below a 90% bar. An effect spread across an arm that was a fifth to half untreated reads as nothing, *"and no amount of additional users fixes that."*

**Rule:** a treatment-reach gate (≥ 90% of eligible users within a first-contact SLA) and a shakedown week before counting. → `designing-holdout-experiments`, `writing-decision-readouts`

## 2. The targeting failed, not the routing

Every state got a coherent message. But of Homeschool's 848 sends, **623 (73%) went to households whose child was already added and active**. Those households convert at 57–59% regardless. The 149 households that had logged in but not added a child converted at **4.0%**, against 46.8% once a child was added. They got **116 sends**, when a 3-email cap would have allowed about 450.

> *"This is a targeting failure, not a delivery failure and not a copy failure."*

**Rule:** the success state is no-send. That moves about three-quarters of the budget to where it can matter. *"That reallocation is the intervention."* → `designing-lifecycle-states`

## 3. The indicator fired after the decision

Homeschool's original indicator was "3+ pets in 14 days", validated against 12-week retention. The trial is 7 days. Re-scored inside the trial, it **ranked fifth of seven**.

**Rule:** the indicator must fire inside the decision window. → `finding-leading-indicators`

## 4. The indicator was the wrong person's action

The parent reads the email; the child earns the pets. Every top candidate was a child behaviour. The real cliff was a parent action: **adding a child (4.0% → 46.8%)**. As an indicator, "parent adds a child within 7 days" scored lift × coverage ≈ **47.3**, against **9.4** for the old one.

**Rule:** the indicator must be something the email's reader can do. → `finding-leading-indicators`

## 5. Nothing vs something

As the pet threshold rose, conversion-if-hit barely moved (56.2% → 58.7%) while conversion-if-miss climbed (34.2% → 44.7%). Pet depth (< 2 vs 2+) differed by 2.2pp (Holm p = 0.676). The add-child gap was 42.7pp (p ≈ 2e-18).

**Rule:** look for the first gate; don't route on depth. → `finding-leading-indicators`, `designing-lifecycle-states`

## 6. Denominators lie, in both directions

- A Homeschool indicator rate of **88%** only counted parents who had logged in. Over every assigned user it was **58.55% (808/1,380)**.
- Reach was first reported as 54% (all assigned) and corrected to 80% (eligible).

**Rule:** print the denominator rule next to every rate, and show the all-assigned view beside the eligible one. → all readouts

## 7. The per-protocol trap

"Contacted treatment converted at **67.42%**, control at **47.72%**." Being contacted selects for users with data, a valid address, a sendable state and a mature window. *"This is the classic per-protocol fallacy."*

**Rule:** intent-to-treat only. The readout never computes a contacted-vs-uncontacted comparison. → `writing-decision-readouts`

## 8. Moving the behaviour didn't move the outcome

VIP's treatment raised the indicator (≥ 1 course in 4 days) from 57.7% (56/97) to 69.4% (129/186), +11.6pp, p = 0.051. Conversion: 76.7% (66/86) vs 76.8% (136/177), +0.1pp. In the control arm, indicator hitters converted at 75.5% (n = 49) vs 78.4% (n = 37) for non-hitters. The chosen behaviour didn't predict conversion once randomised, and a ~77% baseline left little headroom.

**Rule:** measure the mechanism and the outcome separately, and promise only what δ says. → `writing-decision-readouts`

## 9. A config field nobody reads is not a control

- The design said 3 emails; the code cap had drifted to 5.
- The 24-hour spacing value was in config, and no sender read it.
- Drafts rendered at queue time went out later with stale facts.

**Rule:** enforce caps, spacing and state match inside the send; render at the last responsible moment. → `designing-state-journeys`

## 10. Overloaded states and ordering bugs

- `SIGNED_UP_NO_LOGIN` mixed "never logged in" with "logged in, no child" under one CTA, "Open Typesy". The decisive group got a false premise.
- An earlier `AT_RISK` rule ran before the no-child check, so families with no child were told to restart their child's lessons.

**Rule:** one ask per state; prerequisites before risk states; audit reachability. → `designing-lifecycle-states`

## 11. Missing isn't negative, and "active" isn't "ever"

- Outcome booleans defaulted to `false`, so unmeasured users counted as non-converters.
- A query used `is_active = true`, which meant "in the latest import", not "ever seen". It made 257 users look invisible; all had been seen.

**Rule:** keep "unmeasured" and "unobservable" explicit. → `writing-decision-readouts`, `designing-lifecycle-states`

## 12. Segments are strata, not separate programs

Homeschool was 75% yearly (1,048) and 25% monthly (350). Separate content per cadence would have left about 175 monthly users per arm. The old data showed a tempting interaction (yearly −0.7pp, monthly +3.6pp), but it was noise at that size.

**Rule:** randomise within strata, share the content, and pre-register the interaction. *"Then it is a test. Found afterwards, it is a story."* → `designing-holdout-experiments`

## 13. No bandits at this volume

VIP saw about 4–5 trial starts a day. Testing conversion at the expected effect would take about 920–1,150 days. At that scale per-user optimisation learns noise.

**Rule:** slow, fixed, sealed cycles with a human decision at the end. → `designing-holdout-experiments`

---

*If you've hit one of these yourself, open an issue or PR with your own numbers. Lessons with data are the most useful contribution to this repo.*
