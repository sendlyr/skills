# Assignment, strata, control, and the reach gate

## Deterministic hash assignment

```
u = int(sha256(f"{salt}:{stratum}:{user_id}").hexdigest()[:13], 16) / 16**13
treatment if u < allocation_treatment
```

- **Reproducible:** anyone can recompute any user's arm from the salt.
- **Never re-drawn:** a user keeps their arm forever, including if they come back.
- **One salt per experiment:** reusing a salt correlates arms across experiments.
- **Assign only after the send path works.** Typesy's restart plan made this a rule: never assign arms before sends work. Otherwise the treatment arm fills with untreated users.

## Strata

Use strata for segments you will report separately (billing cadence, platform). The hash is uniform within each stratum. Report each stratum's estimate as a pre-registered diagnostic, never as a way to pick a winner afterwards. If you suspect an interaction, register it as a named secondary hypothesis.

## Control is a route, not an absence

Usually control keeps the existing program. Two rules:

1. **Same delivery machinery where possible**, with the same suppression and unsubscribe handling. Where control copy would contradict the facts (e.g. it assumes a child exists when none does), the send fails closed and is logged.
2. **Attest delivery.** If control is sent by another system, import its delivery summary or attest weekly that it ran. "Control route unverified" means no verdict. Typesy VIP couldn't answer whether its control had received the legacy emails at all, so the comparison might have been emails versus silence.

## The treatment-reach gate

```
due        = eligible treatment users whose first-contact SLA has elapsed
timely     = due users with a successful send (or a correct "not needed" decision) within the SLA
reach      = timely / due          → must be ≥ treatment_reach_min (0.90)
```

- **"Eligible" comes from the sealed population rule**, not from who happened to be contacted. Typesy Homeschool first reported 54% reach against *all* assigned users; against eligible users it was 80.3%. Both numbers belong in the readout. Only the eligible one drives the gate.
- **Timely, not eventual.** A send that arrives after the behaviour window can't rescue delivery.
- **Not needed counts as treated.** If the policy correctly decided not to send (the user was already in a success state), the policy was applied.
- **Every non-contact gets one reason:** never seen, aged out, outage casualty, no queue evidence, queued but not sent, suppressed, or unclassified. The reasons must add up to the total.

Below the gate, the readout says: *"Refused to learn: treatment reach was 87% against a pre-registered 90% minimum, so the treatment arm was not reliably treated. These outcome numbers cannot revise the product hypothesis."* Repair the pipeline, then repeat the same hypothesis; it was never tested.
