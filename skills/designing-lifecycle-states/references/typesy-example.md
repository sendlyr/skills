# Worked example: Typesy Homeschool, from 11 labels to 3 states

Real production figures from 2026, published with permission. Background on the product is in `finding-leading-indicators/references/typesy-example.md`. In short: the parent reads the email, and the child does the lessons.

## What was there

An append-only catalog of 11 labels. Seven could still be emitted by the classifier; four were legacy or historical. The classifier, first match wins:

1. `OUT_OF_SCOPE`: pre-epoch or cancelled (no send)
2. `SIGNED_UP_NO_LOGIN`: no first login, **or** day 0–14 with no children
3. `PAI_HIT`: 3+ pets
4. `AT_RISK`: active child idle ≥ 7 days
5. `STARTED_NO_PAI`
6. `CHILD_NOT_STARTED`
7. `LAPSED_NO_PAI`: fallthrough (no send)

## Where the 848 treatment sends went

| State at send | Sends | Asked the parent to add a child |
|---|---:|---:|
| `PAI_HIT` | 340 | 0% |
| `PAI_PROGRESSING` | 169 | 0% |
| `STARTED_NO_PAI` | 114 | 0% |
| `SIGNED_UP_NO_LOGIN` | 73 | **100%** |
| `CHILD_NOT_STARTED` | 57 | 0% |
| `AT_RISK` | 52 | 0% |
| `ACCOUNT_NOT_CREATED` | 43 | **86%** |

**The routing was not broken.** Each state got a coherent message. **The state model was.** 623 of 848 sends (73%) went to households with an active child, which convert at 57–59% regardless. The 149 households that had logged in but not added a child, converting at 4.0%, got 116 sends in total.

## Defects the audit found

| Defect | Detail |
|---|---|
| Overloaded state | `SIGNED_UP_NO_LOGIN` mixed never-logged-in with logged-in-no-child, under the CTA "Open Typesy" |
| Ordering bug (historical) | `AT_RISK` ran before the no-child check, so no-child households were told to restart their child's lessons, rendered as "your child" |
| Duplicate asks | "Start the first lesson": `NEW`, `CHILD_NOT_STARTED`. "Hatch the next pet": `STARTED_NO_PAI`, `PAI_PROGRESSING`. "Open Typesy": `SIGNED_UP_NO_LOGIN`, `AT_RISK` |
| Distinction that didn't earn a state | Active < 2 pets vs 2+ pets: 2.2pp, Holm p = 0.676 |
| Misnamed fact | `parent_engagement_score` held no parent action |
| Success state still sending | `PAI_HIT` got 340 emails |

## The restart model

| State | Entry (trial days 0–7) | The one ask | Send |
|---|---|---|---|
| `NO_CHILD_ADDED` | No linked child (login status kept as a reason field) | **Add one child in Typesy Admin** | Yes |
| `CHILD_ADDED_NOT_ACTIVE` | A child is linked, but no child activity yet | **Sit with your child and start the first lesson** | Yes |
| `CHILD_ACTIVE` | Any child is active | None. The activation sequence is complete | **No** |

`EXCLUDED` (with reason codes) and `UNOBSERVABLE` (alert) sit outside the model. The 11 old labels survive only as a read-only reporting dimension.

**What collapsing gave up, and why that's fine:** login-specific welcome copy, separate pet-progress and celebration routes, and continuity with old reports. None of them separated the outcome or changed the ask.

## Segments

Yearly was 1,048 users (74.9%) and monthly 350 (25.1%). Decision: one shared treatment, randomised 50/50 *within* cadence, with both stratum estimates reported. The cadence interaction (yearly −0.7pp, monthly +3.6pp in the old data) was too noisy to act on, so it was pre-registered as a named secondary hypothesis. *"Then it is a test. Found afterwards, it is a story."*
