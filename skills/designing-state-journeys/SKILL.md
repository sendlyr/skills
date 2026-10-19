---
name: designing-state-journeys
description: Design the contact policy and journey for state-routed lifecycle messaging (one ask per state, caps and spacing enforced at send time, re-render at send, human batch release, termination reasons), and audit an existing program's sends to find where the budget really went. Use when building onboarding or activation journeys in Braze, Customer.io, Iterable or your own code, setting frequency caps and send rules, or when an email program sends a lot but moves nothing ("why did our onboarding emails do nothing?"). Produces contact-policy.toml, a send-time checklist, a journey map and a send audit. Hands off to grounding-lifecycle-emails and designing-holdout-experiments.
license: MIT
metadata:
  author: sendlyr
  version: "0.1.0"
---

# Designing state journeys

`designing-lifecycle-states` decides **who** needs which ask. This skill decides **when and how often** they get asked, and makes the policy hold at the moment of sending, where most programs quietly break.

## When to use

- After `designing-lifecycle-states`, before writing any copy.
- When setting caps, spacing, send windows, suppression and exit rules.
- When auditing a program that "showed nothing". Run `audit_sends.py` before blaming the copy.

## Two journey shapes

| | State-routed policy (recommended) | Graph journey |
|---|---|---|
| Shape | At most one message per state the user passes through, plus a total cap | Steps, waits and branches (Canvas / Campaign style) |
| Moves on | The user's current state at each evaluation | State triggers, plus behaviour measured since the last send |
| Why | It is testable as a whole: the treatment is the sealed policy | It can express rich paths, but can't credit individual emails |

Either works. Pick one, write it down, and keep it fixed during a test. Sendlyr ran the state-routed policy in production because it was measurable and safe. `references/journey-patterns.md` covers both, including history-aware variants (a "recovered path" vs a "direct path" version of the same step).

## Method

1. **Start from `states.toml`.** For each sending state, record its ask, its CTA, when it may first send, and its maximum sends. Success and excluded states are no-send.
2. **Write `contact-policy.toml`** from `assets/contact-policy.toml`. It covers:
   - the total cap and the minimum hours between sends;
   - the send window and timezone;
   - the first-contact SLA (how fast a newly eligible user must be reached) and the reach gate;
   - suppression sources and the control route;
   - the termination reasons.
3. **Write the send-time checklist** (`references/contact-policy.md`). Every send re-checks it right before the provider call, and logs every blocked reason.
4. **Render at the last responsible moment.** Templates are approved ahead of time; personal values are filled in at send time from the freshest data.
5. **Release in batches with a human in the loop** for anything experimental. Each batch has a size ceiling and an expiry, moves one way only (`pending → released → sent`), and leaves an audit row. There is no "release all".
6. **Define termination before launch**, so nobody infers it later from the last row:
   - converted;
   - indicator reached;
   - contact budget complete;
   - left eligibility;
   - state changed (the queued message was cancelled);
   - suppressed;
   - pipeline failure.
7. **Map it to your platform** (`references/platform-notes.md`): entry and exit criteria, frequency caps, control groups, and where the state comes from.
8. **Audit what actually happened** once sends exist, including during the shakedown week:

   ```bash
   python3 scripts/audit_sends.py --policy contact-policy.toml --assignments assignments.csv \
     --sends sends.csv [--outcomes outcomes.csv --outcome converted] --out send-audit/
   ```

   It reports:
   - reach against the eligible denominator, within the SLA;
   - where sends went by state, and what share went to users already in a success state;
   - cap, spacing, no-send-state and control-contact violations;
   - sends per user, termination classes, and render-to-send staleness.
9. **Hand off:** content to `grounding-lifecycle-emails`; then seal states, policy and templates together in `designing-holdout-experiments`.

## Gotchas (all real)

- **A config field nobody reads is not a control.** Typesy Homeschool's design said 3 emails; the code cap had drifted to 5. The config said 24 hours between sends; no sender ever read that field. Enforce caps and spacing *inside the send*, from the send log.
- **State equality is coarser than fact equality.** A user can stay in the same state while their facts change (1 pet becomes 2). Re-render at send; don't send a draft rendered yesterday.
- **Queue-time rendering goes stale.** Typesy drafts rendered at queue time waited through shadow-mode runs and retries, then went out with old facts.
- **Send-time state check:** if the user's state changed since the message was queued, cancel it and log `state_changed`.
- **Targeting is the intervention.** In Typesy Homeschool, 73% of sends went to already-active households. The audit's `success_state_send_share` exists to catch that in week one, not month three.
- **Control goes through the same machinery** where possible. If its copy would contradict the facts (it assumes a step the user hasn't taken), fail closed.
- **Opens are not outcomes.** Privacy features inflate them. Use provider delivery for reach, and the product event for the mechanism.

## Run on the example

From the repo root:

```bash
python3 skills/designing-state-journeys/scripts/audit_sends.py \
  --policy examples/practica/experiment-broken/contact-policy.toml \
  --assignments examples/practica/experiment-broken/assignments.csv \
  --sends examples/practica/experiment-broken/sends.csv \
  --outcomes examples/practica/experiment-broken/outcomes.csv --outcome converted --out /tmp/send-audit
```

The broken run reproduces the Typesy pattern: an outage, most sends going to already-active users, cap drift, retries inside 24 hours, stale renders, and a few control users contacted. Compare it with `examples/practica/experiment`.

## References

- `references/contact-policy.md`: the send-time checklist, caps and spacing, batch release, termination taxonomy.
- `references/journey-patterns.md`: state-routed vs graph journeys, branches, deltas since last send, variants, re-entry.
- `references/platform-notes.md`: implementing it in Braze, Customer.io, Iterable or in-house.
- `references/audit-queries.md`: SQL for the seven audit questions, when your data lives in a warehouse.
- `references/typesy-homeschool-audit.md`: the real audit that found where 848 sends went.
- `assets/contact-policy.toml`, `assets/journey-map.md`: templates.
