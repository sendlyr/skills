---
name: writing-decision-readouts
description: Read out a lifecycle, onboarding or activation experiment honestly. It checks delivery and measurement integrity first (treatment reach, control contamination, sample-ratio mismatch, pre-registration drift, missing outcomes), refuses to learn when the test was invalid, then classifies the intent-to-treat result against the pre-registered minimum worthwhile effect (supported, falsified, harmful, inconclusive). Use when an experiment has finished, someone asks "did it work?", a result looks too good or "showed nothing", or a readout needs to go to a CEO or board. Produces a fixed-format readout and a decision record.
license: MIT
metadata:
  author: sendlyr
  version: "0.1.0"
---

# Writing decision readouts

A readout's job is to say what is known, including "no" and "we can't tell". This skill produces a readout in a fixed order:

1. Was the treatment actually delivered?
2. Is the data sound?
3. What was the pre-registered question?
4. What did the randomised arms show?
5. What can't this conclude?
6. What does the team decide?

The effect is classified by a rule sealed before launch, not by the mood of the meeting.

## When to use

- An experiment designed with `designing-holdout-experiments` has reached its `analysis_not_before` date.
- "Did the onboarding emails work?" / "Why did the test show nothing?" / "This lift looks amazing; is it real?"
- Reviewing someone else's experiment claim before it goes to a CEO, board or investor.

## What you need

- `prereg.toml` (and `prereg.lock` if it was sealed).
- `assignments.csv`: arms exactly as randomised.
- `outcomes.csv`: the primary (and mechanism) metric per user. A blank means not measured.
- `sends.csv`: what the treatment pipeline actually did. **Without it, delivery is unverified and there is no verdict.**

Formats: [`docs/data-contracts.md`](../../docs/data-contracts.md).

## Method

1. **Run the readout:**

   ```bash
   python3 scripts/readout.py --prereg prereg.toml --assignments assignments.csv \
     --outcomes outcomes.csv --sends sends.csv --as-of 2026-09-08 --out readout/
   ```

   `--as-of` is the date your data was extracted. Without it, the script uses the latest timestamp in the files, which can sit before `analysis_not_before` and give `NOT_READY`.

2. **Read the gates before the numbers.** If any gate fails, the verdict is `INVALID_*` and the arm difference is hidden. Say so plainly, and quote the refusal sentence from the report. Then help find the cause (`designing-state-journeys` has `audit_sends.py`). Do not look for a subgroup that "worked".
3. **If valid, state the evidence class** exactly as computed (see `references/evidence-classes.md`), with the interval and δ. Never upgrade `INCONCLUSIVE`.
4. **Separate mechanism from outcome.** "The behaviour moved (+X pp), the outcome did not (+0.1pp)" is a real and useful result. It means the indicator was not the lever, or there was a ceiling.
5. **Write the decision record** from `assets/decision-record.md` with the owner. It answers four questions:
   - What did the evidence class say?
   - Which assumption survived or failed?
   - What one thing changes next?
   - What new prediction, with what δ, follows?

   The action (adopt / repeat / revise / stop) is the human's. The evidence class is not editable.
6. **Publish the null, too.** A negative or inconclusive result, stated with its limits, is the most credible thing a growth team can show.

## The rules

- **Intent-to-treat only.** Compare arms as randomised. *Never* compare contacted vs uncontacted users. In Typesy Homeschool, "contacted treatment" converted at 67.42% vs 47.72% for control. That gap is selection, not lift, and it is the classic per-protocol fallacy.
- **Refuse to learn below the reach gate.** *"Refused to learn: treatment reach was 87% against a pre-registered 90% minimum, so the treatment arm was not reliably treated. These outcome numbers cannot revise the product hypothesis."* Repeat the same hypothesis after the repair; it was never tested.
- **Report reach against the eligible population, and show the all-assigned number too.** Typesy Homeschool: 54.16% of all assigned (534/986) vs 80.30% of eligible (534/665). Both were below 90%.
- **Blank outcomes are not negatives.** Count them, and fail the gate when they exceed the sealed share.
- **Don't condition on post-treatment events.** Splitting treatment by "hit the indicator" breaks randomisation. Typesy's VIP readout deliberately omits that subgroup.
- **Hidden until mature.** Before `analysis_not_before`, the readout shows delivery and maturity, not the difference. That protects against stopping early and moving the goalposts.
- **Power is pre-launch.** Compare n against the n required for δ, never "required n" computed from the observed effect.

## Run on the example

From the repo root:

```bash
python3 skills/writing-decision-readouts/scripts/readout.py \
  --prereg examples/practica/experiment/prereg.toml \
  --assignments examples/practica/experiment/assignments.csv \
  --outcomes examples/practica/experiment/outcomes.csv \
  --sends examples/practica/experiment/sends.csv --as-of 2026-07-15 --out /tmp/readout-good
```

Swap `experiment` for `experiment-broken` to see a refusal (`INVALID_DELIVERY`): an outage, sends to already-active users, and control contamination.

## How to explain the result

- First line: the evidence class in plain words. "The test rules out the 2-point lift we needed" is clearer than "p = 0.4".
- Then the numbers: arm rates, difference, interval, δ, n vs required n.
- Then the limits: what this readout can't say.
- For a refusal, lead with the refusal and the cause. Don't show the arm numbers in slides; they will be misquoted.

## References

- `references/evidence-classes.md`: the six classes, what each means, and what to do next.
- `references/refusing-to-learn.md`: every gate, the traps they catch, and Typesy's real failures.
- `references/typesy-vip-readout.md`: a full worked readout of a real experiment, where the indicator moved and conversion didn't.
- `assets/decision-record.md`: the decision template.
