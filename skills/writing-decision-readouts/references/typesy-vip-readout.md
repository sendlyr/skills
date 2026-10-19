# Worked readout: Typesy VIP (real data, 2026)

Typesy VIP is a 7-day trial of eReflect's typing course that converts to paid automatically. Treatment users got state-routed onboarding emails aimed at one indicator: **complete at least one course within the first 4 days**. Published with permission, from the corrected August 2026 data pull.

## The numbers

| Measure | Treatment | Control | Difference (Newcombe 95% CI) |
|---|---:|---:|---:|
| Indicator: ≥ 1 course in 4 days | 69.4% (129/186) | 57.7% (56/97) | **+11.6pp** (−0.0 to +23.3), p = 0.051 |
| Trial conversion | 76.8% (136/177) | 76.7% (66/86) | **+0.1pp** (−10.1 to +11.5) |

(+11.6pp is the exact difference; it is often quoted as +11.7pp from rounded rates.)

## How this skill reads it

**1. Delivery first.** On 9 August 2026, 189 of 269 treatment users (70.3%) had received at least one email. That is below a 90% reach gate, so under this skill's rules **the verdict is `INVALID_DELIVERY`**, and the arm comparison can't revise the hypothesis. This experiment pre-dated the gate; we show the numbers as a teaching example, not as proof.

**2. If delivery had been valid**, the mechanism and the outcome tell different stories:

- **The behaviour moved.** The indicator rose about 12 points, borderline (the interval just touches zero).
- **The outcome didn't.** Conversion moved 0.1 points. The interval runs from −10 to +12, so a moderate effect can't be ruled out.
- With any sensible δ (say +3pp), the outcome would be **`INCONCLUSIVE`**.
- **Leading explanation: a ceiling.** About 77% of control trials converted without any intervention, leaving little headroom. Detecting +5pp from 76.7% would need about 1,034 users per arm; this test had 86 control users with measured conversion.

**3. Was the indicator even predictive?** Inside the control arm, the clean unexposed group, users who hit the indicator converted at **75.5% (37/49)**, against **78.4% (29/37)** for those who didn't: a difference of −2.9pp (−19.9 to +15.6). A behaviour picked because it correlated with conversion showed no relationship under randomisation. That doesn't prove it's useless (the interval is wide), but it removes the reason to believe it was the lever.

**4. What is deliberately not reported.** The treatment-arm split by indicator hit. Hitting the indicator happens after treatment, so conditioning on it breaks randomisation (collider bias).

## The decision record that follows

- **Evidence class:** `INVALID_DELIVERY` (reach 70.3% < 90%).
- **Assumption that failed:** that course completion is the lever for conversion. Inside the control arm, it didn't predict conversion.
- **What changes:** move to a population with headroom (Typesy Homeschool's no-child households, converting at 4%), pick an earlier setup-step indicator, add the reach gate, and seal δ.
- **Action:** revise. A new hypothesis version, with a shakedown week before counting.

## Why publish this

*"We moved the behaviour. Conversion did not move."* A team that can say that, with its limits, is a team whose positive results can be believed.
