# Journey patterns

## State-routed policy

At each evaluation (on an event, or daily), compute the user's state. If it is a sending state that hasn't been messaged and every send-time check passes, send that state's message. Stop when the user reaches success, exhausts the cap, or leaves eligibility.

- **Pros:** simple; testable as one policy; can't route a user "backwards"; no sequence bookkeeping.
- **Cons:** less expressive; a user who jumps straight to success gets nothing, which is usually correct.

## Graph journey

A journey has an entry condition (a set of states), an entry step per state, and steps. Each step has:

- `template` and `wait_hours`;
- `sends_email` (some steps are silent waits);
- `snapshot_on_send`: the facts recorded at send, to compute behaviour since this email;
- `branches`, evaluated in order, first match wins:
  - **state branch:** `state == PRE_CHARGE` → step_2
  - **behaviour branch:** `lessons_completed_delta >= 1` after ≥ 48h → step_2 (the delta is measured against the last send's snapshot)
  - **silence branch:** `activity_since_send == 0` after ≥ 48h → step_1b

Useful mechanics from Sendlyr's engine:

- **Deltas since the last send** (`*_delta`, `activity_since_send`, `hours_since_send`), so branches react to what happened *after* the email.
- **History-aware variants:** the same step reads differently depending on the path. A "recovered path" version thanks a user who came back after going quiet; a "direct path" version builds on fast progress. The conditions are `came_from_step`, `passed_through_step`, `never_visited_step`, combined with all/any.
- **Exit steps** (`EXIT_SUCCESS`, `EXIT_CHURN`, `EXIT_STALLED`) end the journey explicitly.
- **Stall guard:** cap the steps advanced per evaluation, so a bad branch can't loop.
- **Re-entry cooldown:** after exiting, block re-entry for N days (e.g. 30).
- **Rejected drafts don't become the baseline:** if a send is cancelled, remove its snapshot so deltas aren't computed against an email that never went out.

## Choosing

If you will test the program with a holdout, prefer the state-routed policy, or a graph with very few branches. The treatment is the whole policy either way; per-email attribution is not available when users get several emails. *"There is no last-touch fallback, fractional credit, or model-based allocation."* Message-level timings are diagnostics, never a message winner.
