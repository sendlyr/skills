# State rules in depth

## 1. One state, one ask, by the person you email

A state exists to ask the reader for one thing. If you can't write the ask as a single action the reader can take today, the state isn't ready.

| Bad | Why | Better |
|---|---|---|
| `ENGAGED`, ask: "Keep it up!" | Not an action | No-send. The user already succeeded |
| `AT_RISK`, ask: "Open the app" (to a parent whose child does the lessons) | The actor is wrong, and "open" isn't the goal | `CHILD_ADDED_NOT_ACTIVE`, ask: "Sit with your child for their first 15-minute lesson" |
| `TRIAL_DAY_3` | Time is not a state | Route on what the user has or hasn't done; use time only for spacing |

## 2. Success is terminal and no-send

When the indicator is reached, the activation sequence is done. Further "keep going" emails are a *different* program (habit, retention, expansion) with its own hypothesis and its own test. Don't let them ride along on activation's budget.

> Typesy Homeschool: 623 of 848 sends (73%) went to households whose child was already added and active. Those households convert at 57–59% regardless. The 149 households that hadn't added a child, converting at 4.0%, got 116 sends in total, when a 3-email cap would have allowed about 450. Making the success state no-send moves roughly three quarters of the budget to where it can matter. *That reallocation is the intervention.*

## 3. Ladder order

```
UNOBSERVABLE  →  exclusions  →  success  →  nearest step  →  …  →  furthest step  →  fallback
```

- **Prerequisites before risk.** "Inactive for 7 days" means nothing for a user who never finished setup. Check setup first.
- **Success before distance states**, so an active user who also matches an older rule isn't routed backwards.
- **Fallback should be near-empty.** If it fills up, there's a gap in the model.

The audit's `unreachable_state` finding catches the most common ordering bug: a broad early rule that captures everyone a later state was meant for.

## 4. Don't overload a state

A state that mixes two different situations can't have one true premise. Typesy's `SIGNED_UP_NO_LOGIN` held both "never logged in" and "logged in, no child added". Its email assumed the parent hadn't opened the product, which was false for the decisive half, and its CTA was "Open Typesy". The fix was to split by the reader's actual next step.

## 5. Same ask = same state

If two states make the same ask, merge them and keep the difference as a fact. You can still personalise copy with the fact; you don't need a second routing branch.

## 6. Every distinction must separate the outcome

Run the audit on historical facts. For each pair of states, a Fisher exact test checks whether their outcome rates differ, Holm-corrected across all pairs. Distinctions that don't separate (`indistinguishable_pair`) are complexity without targeting. Typesy's pet-depth split (2.2pp, p = 0.676) didn't earn a state; the add-child split (42.7pp, p ≈ 2e-18) did.

Statistical separation is necessary, not sufficient. A pair can separate and still make the same ask; then rule 5 wins.

## 7. Unobservable and excluded live outside the model

- `EXCLUDED` carries a reason code (test, cancelled, pre-epoch, unsupported plan) and is reported, never messaged.
- `UNOBSERVABLE` means required facts are missing. It raises an alert. **It must never quietly become a "lapsed" or "at risk" state.** That turns a tracking bug into a targeting decision.

## 8. Name facts for what they measure

Before routing on a fact, read its formula. Typesy's `parent_engagement_score` was the children's engagement plus a pet bonus, with no parent action in it. A misnamed fact leads to a model that thinks it targets one person while measuring another.

## 9. Segments are strata, not states

Billing cadence, platform, country and plan are **strata**: who the user is, not what they need to do next. Freeze them before randomisation, report results within each stratum, and share one treatment unless a pre-registered test says otherwise. Splitting content by segment divides your sample. Typesy Homeschool was 75% yearly (1,048) vs 25% monthly (350); separate monthly content would have had about 175 users per arm.
