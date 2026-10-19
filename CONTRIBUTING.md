# Contributing

Thanks for helping make lifecycle measurement more honest.

## What helps most

1. **Lessons with numbers.** A real failure mode, with the data that exposed it, added to `docs/lessons.md` and to the relevant skill's Gotchas section.
2. **Export recipes** for more tools in `skills/finding-leading-indicators/references/preparing-data.md`.
3. **New audit checks** in a script, with a planted example in the generator and a test.

## Ground rules

- **Standard library only** for scripts (Python 3.11+). No pandas, numpy, scipy or YAML. Config is TOML.
- **Formats live in `docs/data-contracts.md`.** Change the contract first, then the scripts, then the tests.
- **Shared code is copied, not imported**, because skills install as independent folders. Edit `scripts/shared/*.py`, then run `python3 scripts/sync_shared_blocks.py`.
- **`facts.json` is the public record** that other sites copy: install commands, skill, script and test counts, and network behaviour. If you add a skill, script or test, update it; `tests/test_facts.py` tells you what drifted.
- **Every planted truth has a test.** If you change `datasets/generate_synthetic.py`, regenerate (`python3 datasets/generate_synthetic.py --out examples/practica`) and update `answer_key.json`.
- **No real user data** in issues, PRs or examples. Aggregates only.
- **Keep SKILL.md under 500 lines.** Push detail into `references/`.
- **Plain English.** Short sentences. Predictive is not causal. Say what a number can't tell you.

## Checks

```bash
python3 -m unittest discover -s tests -v
python3 scripts/sync_shared_blocks.py --check
python3 datasets/generate_synthetic.py --out examples/practica --check
python3 scripts/validate_skills.py
```

CI runs all four. If you have Claude Code, also run `claude plugin validate --strict .`.
