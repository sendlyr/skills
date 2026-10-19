# Data contracts

Every script in this repo reads plain CSV and TOML files and writes aggregate reports. This page is the single source of truth for those formats. If a script and this page disagree, the script has a bug.

## Shared rules

- **Python 3.11+, standard library only.** No pandas, numpy, scipy or YAML. Config files are TOML, read with `tomllib`.
- **CSV:** UTF-8, comma-separated, one header row. Column order does not matter. Unknown columns are ignored.
- **Timestamps:** ISO 8601, e.g. `2026-03-01`, `2026-03-01T14:30:00`, `2026-03-01T14:30:00Z` or `2026-03-01T14:30:00+10:00`. A value without a timezone is treated as UTC. A date-only value means midnight UTC.
- **Booleans:** `1/0`, `true/false`, `yes/no`, `y/n` (any case).
- **Blank means unknown**, never `0` or `false`. An unmeasured outcome is not a negative outcome; every script reports blanks separately.
- **IDs are opaque strings.** Reports never print a user, account or message ID. Only the opt-in per-user exception files (`--emit-user-file`) contain IDs, and those are for internal use.
- **Privacy:** scripts read raw rows locally and write aggregates only. Nothing is sent over the network.
- **Output:** every script takes `--out DIR` and writes `report.md` (human-readable) and `result.json` (machine-readable, with `schema_version`). It also prints the Markdown report to stdout.
- **Exit codes:**
  - `0`: the analysis ran. An `INVALID_*` verdict or a refusal is still a successful run.
  - `1`: `claim_check.py` found blockers (unless `--no-fail`).
  - `2`: the input is malformed. The error message names the file, row number and column.

## Condition language

`states.toml`, `contact-policy.toml` and `claim-rules.toml` all use the same small condition language for rules over a row of fields.

```
lessons_completed >= 1
goal_set == 0 and logged_in == 1
plan == "monthly" or plan == "weekly"
(goal_set == 0 or lessons_completed == 0) and cancelled == 0
last_login == null
```

- **Comparisons:** `==`, `!=`, `>`, `>=`, `<`, `<=`.
- **Values:** numbers, double-quoted strings, `true`, `false`, `null`.
- **Combining:** `and` binds tighter than `or`. Parentheses group.
- **Missing fields:** a field that is blank or absent equals `null`. Any comparison other than `== null` or `!= null` is false for a missing value. Missing data never quietly matches a numeric rule.
- **Safety:** there is no arithmetic, no function calls and no `eval`.

The shared implementation is copied into each script that needs it, because skills install as independent folders. The canonical blocks are:

- `scripts/shared/common.py`: parsing, errors, output writing
- `scripts/shared/stats.py`: the statistics below
- `scripts/shared/conditions.py`: this language

A script embeds a block verbatim between its `# --- BEGIN shared:NAME …---` and `# --- END shared:NAME ---` markers. `python3 scripts/sync_shared_blocks.py` refreshes every copy, and `tests/test_shared.py` fails on drift.

---

## Inputs

### `accounts.csv`

Used by `score_signals.py`. One row per account (or user) that started the journey.

| column | required | meaning |
|---|---|---|
| `account_id` | yes | opaque ID |
| `anchor_at` | yes | when the journey starts: signup or trial start |
| `outcome_at` | no | when the outcome happened (e.g. first payment). Blank means not observed |
| `observed_until` | no | the last moment data is complete for this account. Defaults to `--as-of`, or the latest timestamp in the dataset |

### `events.csv`

Used by `score_signals.py`. One row per event.

| column | required | meaning |
|---|---|---|
| `account_id` | yes | matches `accounts.csv` |
| `event_name` | yes | e.g. `lesson_completed` |
| `occurred_at` | yes | timestamp |
| `actor` | no | who performed the action, e.g. `learner`, `parent`, `system` |

`actor` is optional. When present, candidates performed by someone other than `--email-actor` are flagged *not actionable*, because email can only ask the person who reads it to act.

### `facts.csv`

Used by `state_audit.py`. One row per user, holding the facts at the decision point (e.g. day 3), plus the outcome.

| column | required | meaning |
|---|---|---|
| `user_id` | yes | opaque ID |
| *any fact columns* | | referenced by `states.toml` rules |
| *outcome column* | yes | named by `--outcome`. `1/0`, blank = unmeasured |

### `assignments.csv`

Used by `readout.py`, `audit_sends.py` and `holdout.py assign`. One row per randomised user.

| column | required | meaning |
|---|---|---|
| `user_id` | yes | opaque ID |
| `arm` | yes | `treatment` or `control` |
| `assigned_at` | yes | timestamp of randomisation |
| `eligible` | no | `1` (default) if the user could be contacted under the sealed population rule; `0` if excluded by design |
| `exclusion_reason` | no | reason code when `eligible = 0` |
| `stratum` | no | pre-randomisation stratum, e.g. `monthly` or `yearly` |

The arm comes **only** from this file. Arm labels found anywhere else are ignored.

### `outcomes.csv`

Used by `readout.py`. One row per assigned user. Metric columns are named in `prereg.toml`.

| column | required | meaning |
|---|---|---|
| `user_id` | yes | opaque ID |
| *metric columns* | yes | e.g. `converted`, `lesson_done_3d`. Each is `1/0`, blank = not measured yet (immature) or missing |

### `sends.csv`

Used by `audit_sends.py` and `readout.py`. One row per send attempt.

| column | required | meaning |
|---|---|---|
| `user_id` | yes | opaque ID |
| `sent_at` | yes | attempt time |
| `status` | yes | `sent`, `delivered`, `suppressed`, `blocked`, `failed` or `not_needed`. `sent` and `delivered` count as reaching the user. `not_needed` means the policy evaluated the user and correctly chose not to send, e.g. they were already in a success state |
| `state_at_send` | no | the user's state when the message went out |
| `message_key` | no | template or message identifier |
| `rendered_at` | no | when the content was rendered (for staleness checks) |

---

## Config files

### `states.toml`

Used by `state_audit.py` (`designing-lifecycle-states`), and read by `audit_sends.py` through `contact-policy.toml`.

```toml
[model]
name = "trial_activation_v1"
email_actor = "learner"          # who reads the email
decision_window_days = 7         # e.g. trial length

[unobservable]                   # checked first: missing required facts
required_fields = ["goal_set", "lessons_completed"]

[[exclusions]]                   # checked second, in order
name = "EXCLUDED"
when = "is_test == 1 or cancelled == 1"
reason = "test_or_cancelled"

[[states]]                       # checked third, in order; first match wins
name = "ACTIVE"
when = "lessons_completed >= 1"
success = true                   # the leading indicator is reached
send = false                     # success states should not send
ask = ""

[[states]]
name = "GOAL_SET_NO_LESSON"
when = "goal_set == 1 and lessons_completed == 0"
send = true
ask = "Finish your first 5-minute lesson"
actor = "learner"                # who must perform the ask

[[states]]
name = "NO_GOAL"
when = "goal_set == 0"
send = true
ask = "Pick your learning goal"
actor = "learner"

[fallback]                       # nothing matched
name = "UNCLASSIFIED"
```

Evaluation order: `UNOBSERVABLE`, then exclusions, then states, then fallback. Every user lands in exactly one bucket and gets a reason code.

### `contact-policy.toml`

Used by `audit_sends.py` (`designing-state-journeys`).

```toml
[policy]
max_sends_per_user = 3
min_hours_between_sends = 24
first_contact_sla_hours = 48
treatment_reach_min = 0.90
control_contact_allowed = false

[states]
success = ["ACTIVE"]                 # sends here are budget spent on users who already succeeded
no_send = ["ACTIVE", "EXCLUDED", "UNOBSERVABLE"]

[termination]                        # optional; defaults shown
reasons = ["converted", "success_reached", "budget_complete", "over_cap", "stopped_early", "never_contacted"]
```

### `prereg.toml`

Written by the `designing-holdout-experiments` skill and sealed by `holdout.py seal`. Read by `readout.py`.

```toml
[experiment]
name = "practica-trial-activation-2026q2"
hypothesis = "Routing day-0..3 emails by state raises 14-day paid conversion."
mechanism = "More trial users finish a first lesson within 3 days."
unit = "user"
allocation_treatment = 0.5
cohort_start = "2026-04-01"
cohort_end = "2026-05-15"
analysis_not_before = "2026-06-05"

[primary]
metric = "converted"                 # column in outcomes.csv
baseline_rate = 0.40
minimum_worthwhile_effect = 0.03     # absolute (3 percentage points)
direction = "increase"
confidence_level = 0.95

[mechanism]                          # optional
metric = "lesson_done_3d"

[gates]
treatment_reach_min = 0.90
first_contact_sla_hours = 48
max_missing_outcome_share = 0.05
srm_p_min = 0.001
control_contact_allowed = false

[policy]
treatment = "state-routed emails per states.toml + contact-policy.toml"
control = "existing day-based drip"
```

`holdout.py seal prereg.toml` writes `prereg.lock` next to it:

```json
{"file": "prereg.toml", "sha256": "…", "sealed_at": "2026-03-30T09:00:00Z"}
```

The hash covers the file's bytes after line endings are normalised to `\n`. If a lock exists and the hash no longer matches, `readout.py` reports `PREREGISTRATION_DRIFT` and refuses to classify the effect.

### `claim-rules.toml` and `emails.json`

Used by `claim_check.py` (`grounding-lifecycle-emails`).

```toml
[product]
name = "Practica"
forbidden_names = ["Practica Pro", "PRX"]       # internal or plan names that customer copy must not use

[[cta]]
key = "start_lesson"
label = "Start your first lesson"
url = "https://app.practica.example/lesson/first"

[[prohibited]]
phrases = ["guaranteed", "fluent in 7 days"]
level = "blocker"                                # or "warning"
reason = "unsupported outcome claim"

[[patterns]]
regex = "\\b\\d+\\s*(seconds|minutes)\\b"
level = "blocker"
reason = "exact usage metric in copy"

[[fact_rules]]
when = "lessons_completed == 0"
forbid = ["you completed", "you finished", "your first lesson is done"]
level = "blocker"
reason = "claims completion without evidence"

[greeting]
verified_name_field = "first_name"              # fact field holding a verified first name
fallback = "Hi there,"

[required]
footer = true
unsubscribe_token = "{{ unsubscribe_url }}"

[template]
allowed_placeholders = ["first_name", "lessons_completed", "cta_url", "unsubscribe_url"]
```

`emails.json` takes one of two shapes.

**Rendered emails:**

```json
{
  "emails": [
    {
      "id": "e1",
      "state": "GOAL_SET_NO_LESSON",
      "facts": {"first_name": "Ana", "lessons_completed": 0},
      "email": {
        "subject": "", "preheader": "", "headline": "", "intro": "",
        "body": ["", ""], "cta_label": "", "cta_url": "", "footer": ""
      }
    }
  ]
}
```

**A group template plus its per-user renders:**

```json
{
  "template": {"state": "…", "email": {"subject": "…", "intro": "Hi {{ first_name }},", "body": ["…"], "cta_label": "…", "cta_url": "{{ cta_url }}", "footer": "…"}},
  "renders": [{"id": "r1", "facts": {…}, "email": {…}}]
}
```

---

## Script interfaces

| Skill | Script | Command |
|---|---|---|
| finding-leading-indicators | `score_signals.py` | `--accounts F --events F --outcome-window-days N --decision-window-days N [--windows 1,3,7] [--thresholds 1,2,3,5] [--min-users 30] [--holdout-share 0.3] [--email-actor NAME] [--as-of DATE] [--top 10] --out DIR` |
| designing-lifecycle-states | `state_audit.py` | `--states states.toml --facts facts.csv --outcome COLUMN [--min-users 30] [--emit-user-file] --out DIR` |
| designing-holdout-experiments | `holdout.py` | `size --baseline P --mde D [--alpha 0.05 --power 0.8 --allocation 0.5 --eligible-per-week N]`, `assign --users F --salt S [--allocation 0.5] [--stratum-column C] --out F`, `seal FILE`, `verify FILE` |
| writing-decision-readouts | `readout.py` | `--prereg prereg.toml --assignments F --outcomes F [--sends F] [--as-of DATE] --out DIR` (pass `--as-of` = data extraction date) |
| designing-state-journeys | `audit_sends.py` | `--policy contact-policy.toml --assignments F --sends F [--outcomes F --outcome COLUMN] [--emit-user-file] --out DIR` |
| grounding-lifecycle-emails | `claim_check.py` | `--rules claim-rules.toml --emails emails.json [--no-fail] --out DIR` |

## `result.json`: required keys and flag IDs

Tests, evals and the skills read these keys, so their names are fixed. A script may add more keys.

| Script | Required top-level keys | Flag / gate IDs |
|---|---|---|
| `score_signals.py` | `schema_version`, `inputs` (counts: accounts, mature, immature, excluded_outcome_in_window), `candidates` (list; each has `event`, `threshold`, `window_days`, `actor`, `population`, `hits`, `coverage`, `hit_rate`, `miss_rate`, `lift`, `lift_ci`, `relative_lift`, `rank_score`, `readiness`, `flags`, `holdout`), `ranked` (candidate keys `event@>=threshold/windowd` in rank order, actionable only), `recommendation` (`primary`, `supporting`, `caveats`), `nothing_vs_something` (count buckets for the top events), `refused` (e.g. windows beyond the decision window) | `too_broad` (coverage ≥ 0.95), `too_rare` (coverage < 0.05), `not_actionable_actor`, `low_sample`, `negative_lift`, `did_not_replicate`, `window_beyond_decision` |
| `state_audit.py` | `schema_version`, `buckets` (each state/exclusion/unobservable/fallback: `users`, `measured`, `outcome_rate`, `ci`), `pairwise` (state pairs: `p`, `p_holm`, `distinguishable`), `findings` (list of `{id, states, message}`) | `unreachable_state`, `duplicate_ask`, `success_state_sends`, `no_success_state`, `sending_state_without_ask`, `actor_mismatch`, `indistinguishable_pair`, `small_state`, `unobservable_rows`, `unknown_field` |
| `holdout.py` | `size`: `n_control`, `n_treatment`, `n_total`, `weeks` (if a rate was given); `assign`: `counts` by arm and stratum; `seal`/`verify`: `sha256`, `match` | — |
| `readout.py` | `schema_version`, `verdict`, `gates` (list of `{id, passed, value, threshold, message}`), `cohort`, `primary` (`metric`, per-arm `n`, `k`, `rate`, `ci`; `diff`, `diff_ci`, `relative`, `p_value`, `delta_min`, `n_required_per_arm`), `mechanism` (same shape, if registered), `reach`, `limitations` (list of strings), `decision_record` (template fields) | gates: `srm`, `treatment_reach`, `control_contacted`, `prereg_hash`, `missing_outcomes`, `maturity` |
| `audit_sends.py` | `schema_version`, `reach` (eligible, timely, policy coverage, delivered, all-assigned), `sends_by_state` (state, sends, share, `is_success`), `budget` (`success_state_send_share`), `violations` (`cap`, `spacing`, `control_contacted`, counts plus examples without IDs), `termination` (class → users), `staleness` (`p50_hours`, `p90_hours`, `max_hours`) if `rendered_at` is present, `findings` | `reach_gate`, `success_state_sends`, `cap_violation`, `spacing_violation`, `control_contacted`, `no_send_state_sends`, `stale_render` |
| `claim_check.py` | `schema_version`, `summary` (`emails`, `blockers`, `warnings`, `clean`), `results` (per email `id`: `passed`, `severity`, `issues` list of `{family, level, message}`), `template` (if template mode) | families: `prohibited`, `pattern`, `fact_rule`, `cta`, `greeting`, `product_name`, `required`, `unknown_placeholder`, `literal_name_in_template`, `literal_value_in_template`, `cross_user_name` |

## Statistics used (one definition per idea)

- **Rate interval:** Wilson score interval, 95% unless configured.
- **Difference of two rates:** Newcombe's hybrid score interval (method 10), built from the two Wilson intervals.
- **Two-proportion test (reported, never used alone):** pooled z-test, two-sided p-value.
- **State separation:** two-sided Fisher exact test on each pair of states, Holm-adjusted across the family.
- **Sample ratio mismatch (SRM):** chi-square goodness-of-fit against the sealed allocation, 1 degree of freedom.
- **Sample size:** two-sided, two proportions, normal approximation:
  `n_per_arm = (z_{1-α/2}·√(2·p̄·(1-p̄)) + z_{1-β}·√(p1(1-p1) + p2(1-p2)))² / δ²`, adjusted for unequal allocation.
- **Hash assignment** (`holdout.py assign`, and the generator): `u = int(sha256(f"{salt}:{stratum}:{user_id}").hexdigest()[:13], 16) / 16**13`. A user is in treatment if `u < allocation_treatment`. `stratum` is `""` when there is none. Assignment is deterministic and never re-drawn.
- **Treatment reach** (the delivery gate): the share of *eligible* treatment users whose first `sent`, `delivered` or `not_needed` row is no later than `assigned_at + first_contact_sla_hours`. The denominator only counts users whose SLA has elapsed by `as_of`. Readouts also report the plain delivered reach (`sent`/`delivered` only) and the reach over all assigned users, but neither drives the gate.
- **Integrity gates** (`readout.py`). Each gate passes or fails and appears in the report even when it passes:
  - **Assignment:** SRM p ≥ `srm_p_min` (otherwise `INVALID_ASSIGNMENT`).
  - **Delivery:** treatment reach ≥ `treatment_reach_min`; and, unless `control_contact_allowed`, no control user has a `sent`/`delivered` row (otherwise `INVALID_DELIVERY`).
  - **Measurement:** the prereg hash matches `prereg.lock` if a lock exists; the share of blank primary outcomes is ≤ `max_missing_outcome_share` (otherwise `INVALID_MEASUREMENT`).
- **Evidence classes** (`readout.py`), using the confidence interval of treatment minus control and the sealed minimum worthwhile effect δ. The first rule that applies wins:
  1. an integrity gate failed → `INVALID_ASSIGNMENT`, then `INVALID_DELIVERY`, then `INVALID_MEASUREMENT` (the first failing family names the verdict; every failure is listed; no effect classification)
  2. cohort not mature, or `as_of < analysis_not_before` → `NOT_READY`
  3. lower bound ≥ δ → `SUPPORTED_AT_TARGET`
  4. upper bound < 0 → `HARMFUL`
  5. upper bound < δ → `FALSIFIED_AS_WORTHWHILE`
  6. otherwise → `INCONCLUSIVE`

  For `direction = "decrease"`, flip the sign of the difference first.
