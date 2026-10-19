# Decision record: {{ experiment name }}

Readout: {{ path / date }} · Prereg sha256: {{ hash }} · Owner: {{ name }}

## 1. What did the evidence class say?

> **{{ SUPPORTED_AT_TARGET | FALSIFIED_AS_WORTHWHILE | HARMFUL | INCONCLUSIVE | NOT_READY | INVALID_* }}**
> Primary {{ metric }}: treatment {{ rate }} vs control {{ rate }}, difference {{ diff }} (95% CI {{ lo }} to {{ hi }}), against a pre-registered minimum worthwhile effect of {{ δ }}.

*(Copied from the readout. Not editable.)*

## 2. Which assumption survived or failed?

- Mechanism ({{ metric }}): {{ moved / didn't move, numbers }}
- {{ e.g. "Driving goal-setting raised the indicator, but conversion stayed flat. The indicator is not the lever, or the ceiling (~77%) left no headroom." }}

## 3. What one thing changes for the next cycle?

{{ population | state trigger | timing | message policy | measurement }}. One change, so the next result is interpretable.

## 4. What new prediction follows?

- Hypothesis v{{ n+1 }}: {{ statement }}
- Mechanism: {{ … }}
- Minimum worthwhile effect: {{ δ }}
- Semantic diff from v{{ n }}: {{ what changed and why }}

## 5. Action (the human's call)

- [ ] **Adopt.** Ship the policy (a business action, recorded with its reason).
- [ ] **Repeat.** Same hypothesis. Only for an `INVALID_*` cycle after the repair.
- [ ] **Revise.** New hypothesis version (fill in 4) and a new sealed cycle.
- [ ] **Stop.** Not worth pursuing.

Reason: {{ … }}
Signed: {{ name, date }}
