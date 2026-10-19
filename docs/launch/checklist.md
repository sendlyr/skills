# Launch-day checklist

Work in this order. **✋** means the founder approves it in chat before anyone does it. **👤** means the founder does it in their own account. Claude can't do those steps.

Two rules apply throughout:

- Don't publish an install command anywhere until it has worked from a clean folder.
- The essay is the centrepiece of the launch, and the directory is the main channel. Show HN is optional, not the plan.

## Before the day

1. ✋ **Merge the launch-drafts PR** (this folder).
2. **Verify the install commands that are already public in `README.md`**, from a clean folder. Fix the README first if one fails.
   - Claude Code: `/plugin marketplace add sendlyr/skills`, then `/plugin install sendlyr@sendlyr`. Then ask for `finding-leading-indicators` on `examples/practica`.
   - ✋ `npx skills add sendlyr/skills`. This also makes skills.sh list the repo, through the CLI's anonymous install telemetry.
   - Manual: copy one `skills/<name>/` folder into `.claude/skills/` and check that it loads.
3. 👤 **Submit to Anthropic's directory now** at claude.ai/directory/manage. A person reviews every new listing, so start early. Follow [`anthropic-directory.md`](anthropic-directory.md). Keep auto-publish off.
4. ✋ **Choose the release commit.** If other PRs are open, release from `main` as it is, or wait for them. Don't release half of a change.
5. ✋ **Date the changelog.** One-line PR: in `CHANGELOG.md`, change `## 0.1.0 (unreleased)` to `## 0.1.0 (YYYY-MM-DD)`.

## Launch day

6. **Run the checks on the release commit.** CI must be green, and the tag must equal the version in `plugin.json`.
   ```bash
   python3 -m unittest discover -s tests -v && python3 scripts/sync_shared_blocks.py --check
   python3 datasets/generate_synthetic.py --out examples/practica --check && python3 scripts/validate_skills.py
   claude plugin validate --strict .
   grep '"version": "0.1.0"' .claude-plugin/plugin.json
   ```
7. ✋ **Tag v0.1.0:** `git tag -a v0.1.0 -m "v0.1.0" <release-commit> && git push origin v0.1.0`
8. **Build one zip per skill** from the tag, outside the repo (zips must never be committed):
   ```bash
   DIST=$(mktemp -d)
   for d in skills/*/; do n=$(basename "$d"); git archive --format=zip --prefix="$n/" -o "$DIST/$n.zip" "v0.1.0:skills/$n"; done
   ```
9. 👤 **Test one zip on claude.ai before the release goes public.** Open **Customize > Skills > + > Create skill > Upload a skill** and upload `finding-leading-indicators.zip`. Then ask it to run on the Practica example. The release notes give these exact steps.
10. ✋ **Publish the GitHub release.** Make it a full release, not a draft or prerelease.
    ```bash
    gh release create v0.1.0 --verify-tag --title "v0.1.0: six lifecycle measurement skills" \
      --notes-file docs/launch/release-v0.1.0.md "$DIST"/*.zip
    ```
    Then check that it shows as **Latest** and that the `v0.1.0` links in the notes open.
11. ✋ **Badge.** Check it with `curl -sL https://www.skills.sh/b/sendlyr/skills | grep -o 'aria-label="[^"]*"'`. Once it no longer says "resource not found", open the README PR from [`skills-sh-badge.md`](skills-sh-badge.md).
12. ✋ **ComposioHQ/awesome-claude-skills PR.** It is the only list that takes a new repo. Entry in [`awesome-lists.md`](awesome-lists.md) §1.
13. 👤 **Post the essay** on LinkedIn, then on X ([`launch-post.md`](launch-post.md)).
14. 👤 **Share the essay in creator communities** you already take part in: lifecycle, growth, and Claude Code or agent-skills groups. Post once in each, with the story first and the link second.
15. **For the first few hours,** reply to comments, issues and PRs. Write down every question. Each one is a README fix or a lesson.

## After the day

16. **Export GitHub traffic every week.** GitHub keeps only 14 days of traffic data. Save it outside this public repo:
    ```bash
    D=~/Sendlyr/launch-metrics/$(date +%F); mkdir -p "$D"
    for e in views clones popular/referrers popular/paths; do gh api "repos/sendlyr/skills/traffic/$e" > "$D/${e//\//-}.json"; done
    gh api repos/sendlyr/skills --jq '{stars: .stargazers_count, forks: .forks_count, watchers: .subscribers_count}' > "$D/repo.json"
    ```
    Use stars, forks, referrers and issues from outside users as traction signals. skills.sh install counts can be inflated, so don't quote them as proof.
17. 👤 **On or after 2026-11-03:** submit the awesome-claude-code web form ([`awesome-lists.md`](awesome-lists.md) §2). A person has to submit it in the browser.
18. ✋ **On or after 2026-11-03, once the repo has 20 stars:** heilcheng/awesome-agent-skills PR (§3).
19. ✋ **Once there is real usage** (outside issues, PRs and forks): VoltAgent/awesome-agent-skills PR (§4).
20. ✋ **Clean up:** delete `docs/launch/`. Every plugin install clones the whole repo, and the directory scans it.
21. **Optional follow-ups:** shrink the example CSVs below 256 KiB, so directory versions stop being held. Add `"displayName": "Sendlyr"` to `plugin.json`. Link the release from sendlyr.com, which lives in a separate repo.
