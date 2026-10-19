# Platform notes

These are implementation patterns, not product documentation. Check your platform's current docs for exact names and limits.

## Where the state comes from

Compute the state **outside** the messaging platform: in your warehouse, a reverse-ETL job, or your backend. Push it as one user attribute (e.g. `activation_state`) plus the facts the copy needs. Keep the state rules in `states.toml` as the single source of truth. Don't re-implement them as a tangle of segment filters.

## Braze

- **Entry:** a Canvas or Campaign triggered when `activation_state` changes to a sending state, or a scheduled audience check on that attribute.
- **Exit:** exit criteria on `activation_state` becoming a success or no-send state, and on conversion.
- **Caps:** global frequency capping plus a per-Canvas cap. Still verify caps against delivery data.
- **Control:** a Canvas control variant for a program-level holdout. A global control group exists too; decide which is your experiment's control and document it.
- **Re-render at send:** Liquid renders at send time, so pull the facts from attributes or Connected Content, not baked-in values.

## Customer.io

- **Entry:** a segment-triggered campaign on `activation_state`, or an event-triggered campaign on the state-change event.
- **Exit:** exit conditions when the user leaves the segment or converts.
- **Caps:** message limits and frequency settings. Verify against the delivery log.
- **Control:** a holdout or random cohort branch in the campaign. Measure on the conversion goal, not on opens.

## Iterable

- **Entry:** a journey triggered on a user-update or custom event for the state change.
- **Exit:** exit rules on state and conversion.
- **Caps:** frequency management. Verify against the delivery log.
- **Control:** journey holdout groups or experiment holdouts.

## In-house (cron or worker)

Follow the send-time checklist literally, in one transaction with the send-log write. Add human batch release for experiments. Log every blocked reason.

## Whatever the platform

- Export the send log (user, time, status, state at send, template, render time) to run `audit_sends.py`.
- Export assignments from wherever randomisation happened. Never infer arms from platform segment names.
