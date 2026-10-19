---
name: designing-lifecycle-states
description: Turn a leading indicator into a small, testable user-state model (priority ladder, one ask per state, a no-send success state) and audit an existing model for overloaded states, ordering bugs, duplicate asks and distinctions that don't earn their place. Use when designing onboarding or lifecycle segments, deciding who should get which message, mapping users to states for Braze, Customer.io or Iterable, or when a lifecycle program sends a lot but moves nothing. Produces states.toml plus an audit report. Hands off to designing-state-journeys.
license: MIT
metadata:
  author: sendlyr
  version: "0.1.0"
---

# Designing lifecycle states

A state model decides **who gets asked to do what**. That makes it the targeting, and targeting is where lifecycle programs quietly fail.

In Typesy Homeschool, every state got a coherent message and the routing worked. But **73% of sends went to households that had already done the key action**. The households stuck before it, converting at 4%, got the fewest emails. *"This is a targeting failure, not a delivery failure and not a copy failure."*

This skill builds a model that spends messages where they can move someone, and checks an existing model for the mistakes that cause that.

## When to use

- You have an indicator (from `finding-leading-indicators`) and need segments or states for messaging.
- You inherited a state or segment list and want to know if it's sound.
- "Our onboarding emails do nothing." Run the audit before rewriting copy.

## What you need

- The **primary indicator** (and optional supporting signal), and the **decision window**.
- **Who reads the email** (the actor), and every step that person can take before the indicator.
- A **facts CSV** for the audit: one row per user, with the facts at the decision point and the outcome (`user_id`, fact columns, outcome). Format in [`docs/data-contracts.md`](../../docs/data-contracts.md).

## Method

1. **List the reader's steps toward the indicator**, in order. For Typesy Homeschool: log in → add a child → child's first lesson. For a SaaS trial: invite teammate → connect data → first report. These are the only things a lifecycle email can ask for.
2. **Build the ladder** in this order; the first match wins:
   1. `UNOBSERVABLE`: required facts are missing. Alert on it, and never let it fall into a "lapsed" state.
   2. Exclusions, each with a reason code (test, cancelled, out of scope).
   3. **Success**: the indicator is reached. It is **no-send** for this sequence.
   4. **Distance-to-indicator states**: one per remaining reader step, nearest the indicator first.
   5. A fallback for anything unmatched. It should be near-empty; if it isn't, the model has a gap.
3. **Give every sending state exactly one ask**: a single action by the reader. Write the ask in the state definition, not just in the copy.
4. **Keep it small.** Typesy Homeschool went from 11 labels to 3 states: `NO_CHILD_ADDED` (ask: add one child), `CHILD_ADDED_NOT_ACTIVE` (ask: start the first lesson together), and `CHILD_ACTIVE` (no send). Login status, pet counts and history became *reason fields*, not states.
5. **Write `states.toml`** from `assets/states.toml` (format in the data contracts).
6. **Run the audit** on historical facts and fix every finding:

   ```bash
   python3 scripts/state_audit.py --states states.toml --facts facts.csv --outcome converted --out state-audit/
   ```

7. **Check that each distinction earns its place.** The audit tests every pair of states with a Fisher exact test (Holm-corrected). Two states that don't differ on the outcome, or that make the same ask, should be merged.
8. **Hand off** to `designing-state-journeys` for contact policy and timing, and `grounding-lifecycle-emails` for content. Then seal the whole policy in `designing-holdout-experiments`.

## Rules the audit enforces

| Finding | Why it matters |
|---|---|
| `success_state_sends` | Messages sent to users who already succeeded are wasted budget. Typesy sent 73% of its emails there |
| `unreachable_state` | An earlier rule swallows its users. Typesy's old `AT_RISK` check ran before the no-child check, so families without a child were told to "restart your child's lessons" |
| `duplicate_ask` | Same ask means one state. Two states asking "hatch the next pet" add complexity, not targeting |
| `indistinguishable_pair` | The distinction doesn't separate outcomes. Typesy: < 2 pets vs 2+ pets differed by 2.2pp (Holm p = 0.676); no child vs child added differed by 42.7pp |
| `actor_mismatch` | The ask belongs to someone who doesn't read the email |
| `sending_state_without_ask`, `no_success_state` | The model can't say what it wants or when to stop |
| `unobservable_rows` | Tracking gaps. They must alert, never silently become "lapsed" |
| `small_state` | Too few users to measure or justify |

Also check by hand; no script can do this:

- **Overloaded states.** Typesy's `SIGNED_UP_NO_LOGIN` mixed "never logged in" with "logged in, no child", under one CTA: "Open Typesy". The decisive group was told a false premise.
- **Misnamed facts.** Check that each fact measures what its name says.

## Run on the example

From the repo root:

```bash
python3 skills/designing-lifecycle-states/scripts/state_audit.py \
  --states examples/practica/states/states.flawed.toml \
  --facts examples/practica/observational/facts.csv --outcome converted --out /tmp/states-flawed
```

The flawed model has five planted problems (see the comments in the file). `states.toml` is the corrected 3-state version.

## How to explain the result

- Show where users sit, e.g. "31% of trial users are already `ACTIVE` and shouldn't get activation emails; 40% haven't set a goal." (These figures are from the Practica example.)
- For each finding, give the one-line fix.
- Recommend the smallest model that keeps every real cliff.

## Gotchas

- **The success state must stop the sequence.** "Celebrate and push for more" emails to already-active users feel productive. They are where the budget goes to die.
- **Order is logic.** Check prerequisites (setup not done) before risk states (inactive).
- **Don't route on downstream depth.** Pet counts, streak length and lesson totals rarely change who needs which ask.
- **Missing is not lapsed.** In Typesy, `is_active = true` meant "in the latest import", not "ever seen", and a whole bucket was briefly misread as invisible users.
- **Segments like monthly/yearly are strata, not states.** Randomise within them and report both. Don't build separate content for each unless a pre-registered test says so; it splits the sample (Typesy: 1,048 yearly vs 350 monthly).

## References

- `references/state-rules.md`: the rules in depth, with good and bad examples.
- `references/typesy-example.md`: from 11 labels to 3 states, with the real numbers.
- `assets/states.toml`: the template.

## Next

`designing-state-journeys`, then `grounding-lifecycle-emails`, then `designing-holdout-experiments`.
