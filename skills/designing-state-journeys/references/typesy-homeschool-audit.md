# The real audit: where 848 Typesy Homeschool sends went

Real production figures from 2026, published with permission.

## The question

The Homeschool experiment compared state-routed emails (treatment) against the existing fixed drip (control). The indicator hit rate came out at 58.62% vs 58.38%: nothing. Was the copy bad, the routing broken, or something else?

## What the audit found

**Delivery:** 534 of 665 eligible treatment households were reached (80.30%), below a 90% gate. The 131 unreached were mostly casualties of a pipeline outage.

**Routing:** correct. Each state got a coherent message. The no-child states asked the parent to add a child 100% and 86% of the time; `CHILD_NOT_STARTED` correctly asked for a first lesson.

**Targeting: broken.**

| State at send | Sends | Past the key action? |
|---|---:|---|
| `PAI_HIT` | 340 | yes |
| `PAI_PROGRESSING` | 169 | yes |
| `STARTED_NO_PAI` | 114 | yes |
| `AT_RISK` | 52 | yes |
| `SIGNED_UP_NO_LOGIN` | 73 | no |
| `CHILD_NOT_STARTED` | 57 | partly |
| `ACCOUNT_NOT_CREATED` | 43 | no |
| **Total** | **848** | **623 (73%) already past it** |

The 149 households that had logged in but not added a child converted at 4.0%, against 46.8% once a child was added. They got **116 sends in total**, when a 3-email cap would have allowed about 450.

> *"This is a targeting failure, not a delivery failure and not a copy failure."*

**Policy drift:**

- The design cap was 3 emails; the code cap was 5.
- The 24-hour spacing value lived in config and nothing read it.
- Before a later fix, tokens were rendered at queue time and sent later.

**Termination:** there was no defined end, so "completed" mixed "reached the goal" with "used up the budget".

## What changed for the restart

1. Three states. The success state (`CHILD_ACTIVE`) is no-send, which moves about three-quarters of the budget to the 4% group. *That reallocation is the intervention*, and it was pre-registered as the mechanism.
2. Cap and spacing enforced in the send, from the send log.
3. Re-render immediately before the provider call, and store the template revision and facts with every attempt.
4. Human batch release: a ceiling of 500, 26-hour expiry, row lock, and an immutable audit row.
5. Termination reasons defined before launch.
6. A shakedown week gated on ≥ 90% timely reach.
7. Launch gates: zero sub-24h sends, zero over-cap sends, zero no-child messages without the add-child ask, zero state contradictions, zero stale renders.
