# Power and volume

## Size from the minimum worthwhile effect

`holdout.py size` uses the standard two-proportion formula (two-sided α, power 1 − β):

```
n_control = (z_{α/2}·√(p̄(1−p̄)(1 + 1/k)) + z_β·√(p1(1−p1) + p2(1−p2)/k))² / δ²
n_treatment = k · n_control,  k = treatment share / control share
```

Rules of thumb at 80% power, α = 0.05, 50/50:

| Baseline | δ = 2pp | δ = 5pp | δ = 10pp |
|---|---:|---:|---:|
| 10% | 3,841 / arm | 686 / arm | 199 / arm |
| 25% | 7,550 / arm | 1,251 / arm | 329 / arm |
| 50% | 9,806 / arm | 1,565 / arm | 388 / arm |

(Computed with `holdout.py size`; the baseline is the control rate and δ is the absolute lift.)

## Small volume means slow, fixed experiments

Typesy VIP received about 4–5 trial assignments a day. At 50/50:

- about 200 users per arm, enough to test the *indicator*, takes roughly 80–100 days;
- about 2,300 per arm, enough to test *conversion* at the expected effect, takes roughly 920–1,150 days.

At that volume, per-user optimisation (bandits, RL, "learning" journeys) would mostly optimise noise. The honest loop is slow and human-owned: seal a hypothesis, run a fixed holdout, read it once at maturity, decide, repeat.

## Ways to make a test feasible

1. **Raise δ.** Ask what lift the program *must* deliver to be worth running.
2. **Target the cliff.** An intervention aimed at the users with the most headroom (Typesy's 4%-converting no-child households) has a larger possible effect.
3. **Test the mechanism first.** The indicator usually moves more than the outcome, so it needs fewer users. Promise only an indicator result from that test.
4. **Avoid ceilings.** Typesy VIP's control converted at ~77%. With so little headroom, a null on conversion was the likely outcome before launch.
5. **Widen the population** with rules known at assignment, never post-assignment filters.

## Required n is a pre-launch number

The readout compares the sample against the n required *for δ*, not for the observed effect. Computing "required n" from the observed effect after the fact is circular. It always says you need a bit more.
