# Journey map: {{ program name }}

Policy version: {{ v }} · states.toml sha256: {{ … }} · contact-policy.toml sha256: {{ … }}

## Shape

- [ ] **State-routed policy:** at most one message per state, with a total cap of {{ N }}.
- [ ] **Graph journey:** steps and branches below.

## Per-state plan

| State | Ask (one action) | CTA key | First send | Repeat? | Max | Exit when |
|---|---|---|---|---|---|---|
| {{ NO_SETUP }} | {{ … }} | {{ … }} | {{ +2h after entering }} | {{ once more after 48h if still here }} | 2 | {{ state changes, or converted }} |
| {{ SETUP_DONE_NO_ACTION }} | {{ … }} | {{ … }} | {{ … }} | {{ … }} | {{ … }} | {{ … }} |
| {{ ACTIVE }} (success) | — | — | **no send** | — | 0 | — |

## Global rules

- Cap: {{ N }} successful sends per user · Spacing: ≥ {{ H }}h · Window: {{ hh–hh tz }}
- Suppression: {{ provider unsubscribes, local list, converted users }}
- Render: at send time from the freshest facts. Approved template version: {{ … }}
- Release: human batch release. Ceiling {{ 500 }}, expiry {{ 26h }}.

## Send-time checklist (runs before every send)

- [ ] User is in the treatment arm (from assignments only)
- [ ] Current state == the state the message was prepared for, and is not a no-send state
- [ ] Not already sent for this state · under the cap · spacing respected · inside the window
- [ ] Not suppressed · not converted · valid address · unsubscribe link present
- [ ] Template approved for the current state model version · personalisation checks pass
- [ ] Kill switch (shadow mode) is off

## Termination reasons

converted · success_reached · budget_complete · left eligibility · state changed (queued message cancelled) · suppressed · pipeline failure

## Control route

{{ e.g. "Existing welcome drip, unchanged, sent through the same provider; weekly delivery attestation." }}
