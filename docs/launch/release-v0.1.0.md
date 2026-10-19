The first public release of Sendlyr skills: six agent skills that add a measurement layer to lifecycle email. They help you:

1. Find the behaviour that *predicts* conversion in your own event data.
2. Build user states around it.
3. Send each state one ask, at the right time.
4. Keep AI-written emails true.
5. Prove the program works with a sealed holdout.
6. Read out the result honestly, including when the answer is no.

The skills come from a real program run with eReflect's Typesy in 2026, mistakes included. See [the lessons](https://github.com/sendlyr/skills/blob/v0.1.0/docs/lessons.md) and [the case study](https://github.com/sendlyr/skills/blob/v0.1.0/docs/case-study-typesy.md).

> *"Neither experiment failed to show an effect. Neither was ever in a condition to measure one."*

## The skills

| Skill | Use it when | Script |
|---|---|---|
| `finding-leading-indicators` | "What should we track? What's our activation metric?" | `score_signals.py`: lift × coverage, leakage and maturity guards, out-of-time check |
| `designing-lifecycle-states` | "Who should get which message?" / "Our emails do nothing." | `state_audit.py`: unreachable states, duplicate asks, Fisher/Holm separation |
| `designing-state-journeys` | Caps, spacing, timing, exits; "where did our sends go?" | `audit_sends.py`: reach, budget by state, cap/spacing violations, staleness |
| `grounding-lifecycle-emails` | Writing onboarding emails with an LLM, safely | `claim_check.py`: false claims, CTAs, names, template leaks |
| `designing-holdout-experiments` | "How many users? How long? How do we prove it?" | `holdout.py`: size, hash assignment, seal/verify |
| `writing-decision-readouts` | "Did it work?" | `readout.py`: integrity gates, evidence classes, decision record |

The skills chain: **indicator → states → journeys → emails → holdout → readout → next hypothesis.** See [the method](https://github.com/sendlyr/skills/blob/v0.1.0/docs/method.md).

## Install

**Claude Code** (plugin):

```
/plugin marketplace add sendlyr/skills
/plugin install sendlyr@sendlyr
```

**Any agent that supports [Agent Skills](https://agentskills.io)** (Codex, Cursor, Gemini CLI, Copilot, OpenCode and others):

```bash
npx skills add sendlyr/skills
```

**Claude.ai:** download a skill's `.zip` from **Assets** below. Open **Customize > Skills**, select **+**, then **Create skill > Upload a skill**. Code execution must be on (**Settings > Capabilities**). Each zip holds one skill folder.

**Manually:** copy any folder under `skills/` into your agent's skills directory (for example `.claude/skills/` or `.agents/skills/`). Each skill is self-contained.

The scripts need **Python 3.11+** and nothing else: no pandas, no installs, no network access. With a local agent, raw data stays on your machine and reports contain aggregates only. On claude.ai, the scripts run in Claude's code execution environment, so the files you upload are processed there.

## Try it in two minutes

The repo ships a synthetic trial app, **Practica**, with known answers planted in it:

```bash
git clone https://github.com/sendlyr/skills && cd skills
python3 skills/finding-leading-indicators/scripts/score_signals.py \
  --accounts examples/practica/observational/accounts.csv \
  --events examples/practica/observational/events.csv \
  --outcome-window-days 14 --decision-window-days 7 --email-actor learner --out /tmp/signals
```

Or ask your agent: *"Use finding-leading-indicators on examples/practica and tell me what to track."* The [README](https://github.com/sendlyr/skills/blob/v0.1.0/README.md#try-it-in-two-minutes) has two more examples, including a broken experiment for the readout to refuse.

## Also in this release

- **Practica**, a synthetic dataset with an answer key, and the generator that rebuilds it.
- **136 tests** (unit and end-to-end) that run every script against the planted answers. CI runs them on Python 3.11 and 3.13.
- **Docs:** the method, the lessons from Typesy, the Typesy case study and the data contracts.

## What these skills will not do

- They don't call a predictive indicator causal. Only a holdout readout makes a causal claim.
- They don't give a verdict on an invalid test. Below the delivery gate, or with broken randomisation, the readout refuses to learn.
- They don't send email. The agent proposes; a human approves every send.

## Feedback

Open an issue or a PR. Lessons with real numbers are the most useful contribution. See [CONTRIBUTING.md](https://github.com/sendlyr/skills/blob/v0.1.0/CONTRIBUTING.md).

MIT licence. The Typesy figures are published with eReflect's permission.
