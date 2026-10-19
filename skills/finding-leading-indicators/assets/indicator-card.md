# Indicator card: {{ product }}

**Status:** candidate (predictive, not causal). Not yet tested with a holdout.

## The outcome contract (written before scoring)

| | |
|---|---|
| Outcome | {{ e.g. paid within 14 days of trial start }} |
| Anchor | {{ e.g. trial start }} |
| Decision window | {{ e.g. 7 days (trial length) }} |
| Email reader (actor) | {{ e.g. learner }} |
| Data | {{ accounts, date range, as-of date }} |
| Excluded | {{ immature: N · outcome inside behavior window: N · other: N }} |

## Primary indicator

> **{{ behavior in plain words, e.g. "Sets a learning goal within 3 days" }}**
> Rule: `{{ event }} >= {{ threshold }} within {{ window }} days of {{ anchor }}`

| | Did it | Didn't | Difference |
|---|---:|---:|---:|
| Users | {{ hits }} | {{ misses }} | |
| Reached the outcome | {{ hit rate }} | {{ miss rate }} | **{{ lift }}pp** (95% CI {{ lo }} to {{ hi }}) |

- Coverage: {{ coverage }} of eligible users do it.
- Lift × coverage: {{ rank score }}.
- Replicated on the newest {{ holdout share }} of accounts: {{ yes/no, holdout lift and CI }}.
- Actor: {{ actor }}, who reads the email: {{ yes/no }}.

**Nothing vs something:** {{ e.g. "0 events: 3.7% · 1 event: 37% · 3+ events: 38%. The gap is almost entirely between none and one." }}

## Supporting signal (optional)

> {{ behavior }}. {{ one line of numbers }}

Use it to route users who have already cleared the primary gate. Do not stack thresholds.

## Rejected candidates (and why)

| Candidate | Why not |
|---|---|
| {{ e.g. app_opened ≥1 in 1 day }} | {{ too broad: 98% coverage }} |
| {{ e.g. email_opened ≥1 in 3 days }} | {{ weak lift; likely confounded by motivation }} |
| {{ e.g. streak_reminder_shown }} | {{ done by the system, not the reader }} |
| {{ e.g. lessons ≥5 in 14 days }} | {{ fires after the decision window }} |

## Caveats (keep these in every copy of this card)

1. **Predictive, not causal.** Users were not randomised on this behavior. Motivated users may simply do more of everything. Only a holdout that drives the behavior and measures the outcome can show it matters.
2. **{{ N }} candidates were scored.** Some will look predictive by chance. That is why the out-of-time check matters.
3. **Exclusions:** {{ immature and leakage exclusions, and any other filters }}.

## Next step

Design states around distance to this indicator (`designing-lifecycle-states`). Then pre-register a holdout that tests whether moving it changes the outcome (`designing-holdout-experiments`).
