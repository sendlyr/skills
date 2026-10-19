# The method

Lifecycle programs usually fail quietly. They pick a behaviour from a correlation, send a lot of email around it, and report sends and opens. Nobody can tell whether anything changed. This method is the opposite: find a candidate, aim messages only where they can move someone, and let a sealed holdout say yes, no or "can't tell".

```
 1. finding-leading-indicators     which early behaviour predicts the outcome?   (predictive)
 2. designing-lifecycle-states     who is how far from it, and what's their one ask?
 3. designing-state-journeys       when, how often, and when to stop, enforced at send
 4. grounding-lifecycle-emails     what to say, true for this user, checked before review
 5. designing-holdout-experiments  seal the question, size it, randomise, gate delivery
 6. writing-decision-readouts      integrity first, then one evidence class, then a decision
                                   └──► new hypothesis version ──► back to 2 (or 1)
```

## The steps

| # | Step | In | Out | Decides |
|---|---|---|---|---|
| 0 | Data access | Your export | `accounts.csv`, `events.csv` (no PII, aggregates leave your machine) | Human |
| 1 | Outcome contract | Business goal | Outcome, window, anchor, decision window, email reader | Human |
| 2 | Candidates and scoring | Events | Ranked candidates: lift × coverage, CI, holdout replication, flags | Script |
| 3 | Indicator | Scorecards | One primary indicator plus one supporting signal, labelled *predictive* | Human |
| 4 | States | Indicator | `states.toml`: exclusions → success (no-send) → distance states → fallback | Human, audited by script |
| 5 | Contact policy | States | `contact-policy.toml`, send-time checklist, termination reasons | Human, audited by script |
| 6 | Content | Product memory, facts | Objective JSON → copy JSON → claim check → render → **human approval** | AI drafts, human approves |
| 7 | Pre-registration | Hypothesis, δ | Sealed `prereg.toml` (hash), sample size, assignments | Human, before the first assignment |
| 8 | Shakedown | Pipeline | ≥ 90% timely reach, no gaps, every non-contact explained | Gate |
| 9 | Run | — | Daily integrity checks; weekly 15-minute look, no arm difference | — |
| 10 | Readout | Assignments, outcomes, sends | Gates → evidence class → limitations | Script classifies |
| 11 | Decision | Readout | Adopt / repeat / revise / stop, with a new hypothesis version | Human |

## Principles

1. **The agent proposes, the human decides.** AI never chooses recipients, never sends, never writes raw HTML, and never approves its own analysis.
2. **Predictive until proven causal.** Indicator lift and outcome lift are never merged. Correlation picks the candidate; the holdout decides.
3. **Targeting is the intervention.** Success states don't send. Every sending state makes one ask the reader can act on.
4. **Enforce policy at the moment of sending:** caps, spacing, state match, suppression, render freshness.
5. **Refuse to learn from an invalid test.** Below the reach gate, or with broken randomisation or drifted pre-registration, there is no verdict.
6. **Intent-to-treat only.** Never compare contacted against uncontacted users.
7. **Blank is not no.** Unmeasured outcomes are reported, never counted as negatives.
8. **Fail closed.** Missing configuration means no send. Missing data means `UNOBSERVABLE`, never "lapsed".
9. **Publish the nulls.** "We moved the behaviour; conversion did not move" is a result.
10. **No bandits at small volume.** Slow, fixed, human-owned cycles beat online optimisation that learns noise.

## What this method is not

- Not a messaging optimiser. It doesn't pick the best subject line or send time per user.
- Not attribution. With several messages per user, no single email gets causal credit.
- Not a dashboard. A readout with no recorded decision is still an open loop.

See [`lessons.md`](lessons.md) for where each principle came from.
