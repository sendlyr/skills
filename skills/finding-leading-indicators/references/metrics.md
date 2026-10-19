# Metrics, flags and readiness

All numbers are computed on **mature** accounts, those whose outcome window has fully passed. Ranking uses the older **discovery** share of accounts; the newest share is held out to check replication.

## Candidate

A candidate is a rule: **event `E` happened at least `T` times within `W` days of the anchor.** The grid is every event × `--thresholds` × `--windows`.

- **Windows longer than the decision window are refused, not scored.** You can't act on a behavior that only shows up after the user has already decided.
- **Events with fewer than `--min-users` accounts are skipped**, because a handful of users can't support a claim.

## Population and leakage guard

For window `W`, the population is mature accounts **minus** those whose outcome happened before `anchor + W`. Their behavior inside the window may be a *consequence* of the outcome, e.g. a billing page viewed after paying. Only events inside `[anchor, anchor + W)` count.

> Naive analysis of the bundled Practica data shows `billing_page_viewed` at 93% conversion vs 4%: a "perfect" signal. With the guard it is a rare, weak one. That gap is what leakage looks like.

## Metrics

| Metric | Formula | Read it as |
|---|---|---|
| `coverage` | hits / population | How many users already do it |
| `hit_rate` | outcomes among hits / hits | Outcome rate for users who did it |
| `miss_rate` | outcomes among misses / misses | Outcome rate for users who didn't |
| `lift` | hit_rate − miss_rate | Absolute separation, in percentage points |
| `lift_ci` | Newcombe hybrid score 95% interval | Uncertainty on the separation |
| `relative_lift` | lift / miss_rate | "x% more likely". Easy to overstate, so lead with absolute numbers |
| `rank_score` | lift × coverage | How much of the population the separation applies to. `result.json` stores it as a fraction (0.199); the report shows points (19.9 = +33.2pp × 59.8%), the same scale as the Typesy example (47.3) |

**Why lift × coverage:** a behavior with huge lift that 2% of users do is a niche; one that 98% do separates nobody. The product rewards behaviors that are both common and discriminating. Sendlyr used three ranking formulas over time (50/50 hit-rate-and-coverage, recall-based, lift × coverage) and settled on this one because it is the easiest to explain and hardest to game.

## Flags

| Flag | Rule | What to do |
|---|---|---|
| `too_broad` | coverage ≥ 95% | Not a signal. Look for the next step down the funnel |
| `too_rare` | coverage < 5% | A niche. Don't build the program around it |
| `low_sample` | population < min, or < 5 in any cell | Collect more data before deciding |
| `negative_lift` | lift < 0 | The behavior goes with *worse* outcomes. Investigate, don't drive |
| `not_actionable_actor` | `actor` ≠ email reader | Email can't ask this person to act. Find the reader's step that precedes it |
| `did_not_replicate` | holdout lift CI includes 0 | It looked good on old data only. Don't use it |
| `window_beyond_decision` | W > decision window | Fires too late to act on |

## Readiness

| Readiness | Rule |
|---|---|
| `ready` | population ≥ 30; hits, misses, positives and negatives each ≥ 5; lift CI lower bound > 0; replicated (if checked) |
| `directional` | has both hits and misses, but misses a `ready` condition |
| `not_ready` | can't be compared at all |

Only `ready`, replicated, not-too-broad, not-too-rare, actionable candidates can be the **primary** recommendation.

## Out-of-time holdout

Accounts are sorted by anchor date. The oldest 70% (`--holdout-share 0.3`) rank the candidates, and the top ones are re-scored on the newest 30%. This catches two problems:

- **Chance winners.** With dozens of candidates, a few look predictive by luck.
- **Drift.** A product change makes an old signal stale.

It is not a substitute for a randomised test. It only checks that the *correlation* is stable.

## Nothing vs something

For the top events, the report shows outcome rate by count bucket (0, 1, 2, 3–4, 5+) inside the window. If most of the gap is between 0 and 1, the threshold should be 1. Raising the bar mostly selects users who are already engaged, so it measures engagement instead of creating it.

## What these numbers can't tell you

- Whether **driving** the behavior changes the outcome. Motivated users do more of everything.
- Whether the behavior is the **cause** or a **symptom** (e.g. a setup step vs a consequence of setup).
- Anything about users outside the population: immature, excluded, or untracked.
