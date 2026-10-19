# Agent guide (for contributors' coding agents)

- This repo is a set of Agent Skills. Each `skills/<name>/` folder must stay self-contained: SKILL.md + scripts/ + references/ + assets/ + evals/.
- Scripts: Python 3.11+ standard library only. Single file each. Shared code is embedded between `# --- BEGIN shared:NAME` / `# --- END shared:NAME ---` markers; edit `scripts/shared/` and run `python3 scripts/sync_shared_blocks.py`, never edit a copy.
- Input/output formats, flag IDs and statistics are defined in `docs/data-contracts.md`. Treat it as the spec.
- Tests: `python3 -m unittest discover -s tests -v`. Every script is tested end-to-end against `examples/practica/answer_key.json`.
- Never add real customer data. Reports must never print user IDs.
- Before finishing: run the four checks in CONTRIBUTING.md.
