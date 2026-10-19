# Contact policy

## The send-time checklist

Run all of these immediately before each provider call, not when the message is queued. Log every reason a send was blocked.

**Assignment and state**

1. The user is in the treatment arm, from the assignments table only. Ignore arm labels anywhere else.
2. The user's current state equals the state the message was prepared for. If not, cancel and log `state_changed`.
3. The state is not a no-send state (success, excluded, unobservable, out of scope).

**Contact limits**

4. Nothing was already sent to this user for this state.
5. Successful sends < cap, counted from the send log.
6. Hours since the last successful send ≥ spacing.
7. It is inside the send window, in the user's timezone if known.

**Suppression and outcome**

8. The address is not suppressed (provider unsubscribes, local suppression list).
9. The user has not already converted.

**Content**

10. The email address is valid.
11. The unsubscribe link is present.
12. The template is approved for the current state model version.
13. Personalisation validated: no unknown placeholders, no other user's name, no claim the facts don't support. See `grounding-lifecycle-emails`.

**Kill switch**

14. Shadow mode / kill switch is off. **Fail closed:** if the setting is missing, don't send.

## Caps and spacing

- **Count successful sends only.** Dry runs, failures, blocks and suppressions don't consume the cap. Do count retries that went out.
- **Enforce in code, against the send log, in the same transaction as the send.** Typesy's design cap was 3 emails, but the code cap had drifted to 5. The 24-hour spacing value was stored in config and never read.

## Render at the last responsible moment

Approve templates (with placeholders) ahead of time. Fill in personal values at send time from the freshest data, and store with every attempt:

- the rendered content;
- the template revision;
- the snapshot or event version used;
- the state at render and the state at send.

## Human batch release

For experiments and any new program:

- The worker assembles eligible users into one `pending` batch. A dry run returns the same summary without creating anything.
- A named human releases one batch by ID. There is no release-all and no auto-release.
- The release refuses unless the batch is still pending and unexpired, backed by current data, free of control users, and under the size ceiling.
- Batches move only one way: `pending → released → sent`, or `pending → expired / cancelled`. Every release writes an immutable audit row.
- Blocked members are logged; they don't stop safe members from sending.

Typesy's defaults: a ceiling of 500 (enough for peak volume, small enough to stop a classifier bug from mailing thousands) and an expiry of 26 hours (matching data freshness).

## Termination taxonomy

Decide it before launch and record one reason per user:

| Reason | Meaning |
|---|---|
| `converted` | The outcome happened |
| `success_reached` | The leading indicator was reached; the sequence correctly stopped |
| `budget_complete` | Got exactly the planned number of sends |
| `over_cap` | Got more than planned: a defect |
| `left_eligibility` | Aged out, cancelled, excluded |
| `state_changed` | A queued message was cancelled because the state moved |
| `suppressed` | Unsubscribed or suppressed |
| `stopped_early` / `pipeline_failure` | Fewer sends than planned while still eligible: investigate |
| `never_contacted` | No send and no correct "not needed" decision: counts against reach |

"Completed" is ambiguous. Always say which one: reached the goal, or exhausted the budget.
