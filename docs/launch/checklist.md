# Launch-day checklist

Work in this order. **✋** means the founder approves it in chat before anyone does it. **👤** means the founder does it in their own account. Claude can't do those steps.

## Before the day

1. ✋ **Merge the launch-drafts PR** (this folder).
2. ✋ **Choose the release commit.** If other PRs are open, release from `main` as it is, or wait for them. Don't release half of a change.
3. ✋ **Date the changelog.** One-line PR: in `CHANGELOG.md`, change `## 0.1.0 (unreleased)` to `## 0.1.0 (YYYY-MM-DD)`.

## Launch day

4. **Run the checks on the release commit.** CI must be green.
   ```bash
   python3 -m unittest discover -s tests -v
   python3 scripts/sync_shared_blocks.py --check
   python3 datasets/generate_synthetic.py --out examples/practica --check
   python3 scripts/validate_skills.py
   claude plugin validate --strict .
   ```
5. ✋ **Tag v0.1.0.**
   ```bash
   git tag -a v0.1.0 -m "v0.1.0" <release-commit>
   git push origin v0.1.0
   ```
6. **Build one zip per skill** from the tag, outside the repo (zips must never be committed):
   ```bash
   DIST=$(mktemp -d)
   for d in skills/*/; do n=$(basename "$d"); git archive --format=zip --prefix="$n/" -o "$DIST/$n.zip" "v0.1.0:skills/$n"; done
   ls -l "$DIST"
   ```
7. ✋ **Create the GitHub release.**
   ```bash
   gh release create v0.1.0 --verify-tag --title "v0.1.0: six lifecycle measurement skills" \
     --notes-file docs/launch/release-v0.1.0.md "$DIST"/*.zip
   ```
8. **Smoke-test every install path** from a clean folder:
   - Claude Code: `/plugin marketplace add sendlyr/skills`, then `/plugin install sendlyr@sendlyr`.
   - ✋ `npx skills add sendlyr/skills`. This also makes skills.sh list the repo, through the CLI's anonymous install telemetry.
   - 👤 claude.ai: upload `finding-leading-indicators.zip` (**Customize > Skills > + > Create skill > Upload a skill**). Then ask it to run on the Practica example.
9. ✋ **Badge.** Check the badge with `curl -sL https://www.skills.sh/b/sendlyr/skills | grep -o 'aria-label="[^"]*"'`. When it shows a count, not "resource not found", open the one-line README PR from [`skills-sh-badge.md`](skills-sh-badge.md).
10. 👤 **Submit to Anthropic's directory** at claude.ai/directory/manage. Follow [`anthropic-directory.md`](anthropic-directory.md). Expect one policy hold for the large example CSVs. Keep auto-publish off. Review time isn't fixed.
11. ✋ **ComposioHQ/awesome-claude-skills PR.** It is the only list that takes a new repo. Entry in [`awesome-lists.md`](awesome-lists.md) §1.
12. 👤 **Post on LinkedIn**, then on X. Text in [`launch-post.md`](launch-post.md). Add the link in the first comment if you prefer.
13. **For the first few hours,** reply to comments, issues and PRs. Write down every question. Each one is a README fix or a lesson.

## After the day

14. 👤 **On or after 2026-11-03:** submit the awesome-claude-code web form ([`awesome-lists.md`](awesome-lists.md) §2). A person has to submit it in the browser.
15. ✋ **On or after 2026-11-03, once the repo has 20 stars:** heilcheng/awesome-agent-skills PR (§3).
16. ✋ **Once there is real usage:** VoltAgent/awesome-agent-skills PR (§4).
17. ✋ **Clean up:** delete `docs/launch/`. Every plugin install clones the whole repo, and the directory scans it.
18. **Optional follow-ups:** shrink the example CSVs below 256 KiB, so directory versions stop being held. Add `"displayName": "Sendlyr"` to `plugin.json`. Link the release from sendlyr.com, which lives in a separate repo.
