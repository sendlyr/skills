# Sendlyr skills

**The measurement layer under lifecycle.** Six agent skills, with small dependency-free scripts:

1. Find the behaviour that *predicts* conversion in your own event data.
2. Build user states around it.
3. Send each state one ask, at the right time.
4. Keep AI-written emails true.
5. Prove the program works with a sealed holdout.
6. Read out the result honestly, including when the answer is no.

Built from a real program run with eReflect's Typesy in 2026, mistakes included. See [the lessons](docs/lessons.md).

> *"Neither experiment failed to show an effect. Neither was ever in a condition to measure one."*
> That sentence is why these skills check delivery before they show you a lift.

## The skills

| Skill | Use it when | Script |
|---|---|---|
| [`finding-leading-indicators`](skills/finding-leading-indicators/SKILL.md) | "What should we track? What's our activation metric?" | `score_signals.py`: lift × coverage, leakage and maturity guards, out-of-time check |
| [`designing-lifecycle-states`](skills/designing-lifecycle-states/SKILL.md) | "Who should get which message?" / "Our emails do nothing." | `state_audit.py`: unreachable states, duplicate asks, Fisher/Holm separation |
| [`designing-state-journeys`](skills/designing-state-journeys/SKILL.md) | Caps, spacing, timing, exits; "where did our sends go?" | `audit_sends.py`: reach, budget by state, cap/spacing violations, staleness |
| [`grounding-lifecycle-emails`](skills/grounding-lifecycle-emails/SKILL.md) | Writing onboarding emails with an LLM, safely | `claim_check.py`: false claims, CTAs, names, template leaks |
| [`designing-holdout-experiments`](skills/designing-holdout-experiments/SKILL.md) | "How many users? How long? How do we prove it?" | `holdout.py`: size, hash assignment, seal/verify |
| [`writing-decision-readouts`](skills/writing-decision-readouts/SKILL.md) | "Did it work?" | `readout.py`: integrity gates, evidence classes, decision record |

They chain: **indicator → states → journeys → emails → holdout → readout → next hypothesis.** See [the method](docs/method.md).

## Install

**Claude Code** (plugin):

```
/plugin marketplace add sendlyr/skills
/plugin install sendlyr@sendlyr
```

**Any agent** that supports [Agent Skills](https://agentskills.io) (Codex, Cursor, Gemini CLI, Copilot, OpenCode and others):

```bash
npx skills add sendlyr/skills
```

**Manually:** copy any folder under `skills/` into your agent's skills directory (e.g. `.claude/skills/` or `.agents/skills/`). Each skill is self-contained.

The scripts need **Python 3.11+** and nothing else: no pandas, no installs, and no network access. Raw data stays on your machine; reports contain aggregates only.

## Try it in two minutes

The repo ships a synthetic trial app, **Practica**, with known answers planted in it ([`examples/practica`](examples/practica)):

```bash
# 1. Which early behaviour predicts paying?
python3 skills/finding-leading-indicators/scripts/score_signals.py \
  --accounts examples/practica/observational/accounts.csv \
  --events examples/practica/observational/events.csv \
  --outcome-window-days 14 --decision-window-days 7 --email-actor learner --out /tmp/signals

# 2. Is this state model sound? (it isn't: five planted problems)
python3 skills/designing-lifecycle-states/scripts/state_audit.py \
  --states examples/practica/states/states.flawed.toml \
  --facts examples/practica/observational/facts.csv --outcome converted --out /tmp/states

# 3. Did the experiment work? Then try experiment-broken.
python3 skills/writing-decision-readouts/scripts/readout.py \
  --prereg examples/practica/experiment/prereg.toml \
  --assignments examples/practica/experiment/assignments.csv \
  --outcomes examples/practica/experiment/outcomes.csv \
  --sends examples/practica/experiment/sends.csv --as-of 2026-07-15 --out /tmp/readout
```

Or ask your agent: *"Use finding-leading-indicators on examples/practica and tell me what to track."*

## What's different here

- **Tool-agnostic.** CSV in, report out. It works with exports from PostHog, Amplitude, Mixpanel, Segment or a SQL warehouse.
- **Predictive vs causal, kept apart.** Indicators are labelled *predictive*; only a holdout readout makes a causal claim.
- **It can say no.** Readouts compare the interval against a *pre-registered* minimum worthwhile effect: `SUPPORTED_AT_TARGET`, `FALSIFIED_AS_WORTHWHILE`, `HARMFUL` or `INCONCLUSIVE`. Below the delivery gate they refuse to learn.
- **Tested against known answers.** Every script runs in CI against the planted truths in `examples/practica/answer_key.json`.

These skills complement copywriting and marketing skill packs such as [marketingskills](https://github.com/coreyhaines31/marketingskills). Those help you write the email; these tell you who should get it, whether it's true, and whether it worked.

## Repository layout

```
skills/<name>/SKILL.md         the skill (instructions for the agent)
skills/<name>/scripts/         the script (stdlib Python, self-contained)
skills/<name>/references/      deeper docs, loaded when needed
skills/<name>/assets/          templates the skill fills in
skills/<name>/evals/           evaluation prompts and assertions
docs/                          method, lessons, Typesy case study, data contracts
examples/practica/             synthetic dataset and answer key
datasets/generate_synthetic.py regenerates examples/practica
scripts/                       shared code blocks and repo tooling
tests/                         unittest suite (python3 -m unittest)
facts.json                     public facts (install, counts, network) for other sites; checked by tests
```

## Contributing

Lessons with real numbers, export recipes for more tools, and new failure modes for the audits are all welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). The Typesy figures are published with eReflect's permission.
