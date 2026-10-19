# Evidence classes

Computed by `readout.py` from the confidence interval (CI) of treatment − control and the sealed minimum worthwhile effect δ. The first matching rule wins.

| Class | Rule | Say it like this | Usual next step |
|---|---|---|---|
| `INVALID_ASSIGNMENT` | SRM p < threshold | "Randomisation broke; the arms aren't comparable." | Find the assignment bug, then repeat |
| `INVALID_DELIVERY` | Reach below the gate, or control was contacted | "Refused to learn: the treatment arm wasn't reliably treated." | Repair delivery, then repeat the same hypothesis |
| `INVALID_MEASUREMENT` | Prereg drift, or too many missing outcomes | "We can't trust what was measured." | Fix measurement, then repeat |
| `NOT_READY` | Before `analysis_not_before`, or immature | "Too early. The answer is due on {{date}}." | Wait. Don't peek |
| `SUPPORTED_AT_TARGET` | CI lower bound ≥ δ | "The data rule out effects smaller than the target." | Adopt, or replicate before a big rollout |
| `HARMFUL` | CI upper bound < 0 | "It made things worse." | Stop, and understand why |
| `FALSIFIED_AS_WORTHWHILE` | CI upper bound < δ | "The data rule out the lift we promised, though a small effect may remain." | Revise the mechanism, or stop |
| `INCONCLUSIVE` | CI contains δ | "We can't tell. The test didn't answer its question." | Revise (bigger δ, better targeting) or repeat with more power |

## Why compare to δ, not to zero

"Significantly different from zero" turns a tiny, useless lift into a win and an underpowered test into a "no". Comparing to δ, the smallest lift worth the cost, lets a test **falsify** the claim. That makes a useful negative result possible.

## What can't be relabelled

The evidence class is a system output. The owner can still *act* against it for a recorded business reason (e.g. ship an `INCONCLUSIVE` policy because it's cheaper), but the record keeps both.

## Exploratory findings

Strata estimates, message-level timings, opens and clicks are diagnostics. They can inspire the next hypothesis, which then starts with zero causal credit and earns it with its own holdout.
