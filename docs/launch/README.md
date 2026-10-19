# Launch kit for v0.1.0

Drafts for the public launch of `sendlyr/skills`. Nothing here has been published, tagged, posted or submitted yet.

| File | What it is |
|---|---|
| [`checklist.md`](checklist.md) | Launch day, step by step. Start here. |
| [`release-v0.1.0.md`](release-v0.1.0.md) | GitHub release notes, ready for `gh release create v0.1.0 --notes-file`. |
| [`skills-sh-badge.md`](skills-sh-badge.md) | The skills.sh badge line, and why it waits for the first install. |
| [`awesome-lists.md`](awesome-lists.md) | Ready-to-submit entries for four awesome lists, with each list's rules and the earliest date to submit. |
| [`anthropic-directory.md`](anthropic-directory.md) | Submitting to Anthropic's plugin directory: requirements, a pre-check of this repo, and what to enter in each step. |
| [`launch-post.md`](launch-post.md) | LinkedIn post and X versions of "Why our lifecycle experiment showed nothing", with a source for every figure. |

## Approvals needed

Each one is a separate yes:

1. Merge this PR.
2. Date `CHANGELOG.md` for 0.1.0 (one-line PR).
3. Push the `v0.1.0` tag.
4. Create the GitHub release with the six skill zips.
5. Run `npx skills add sendlyr/skills` once. This sends anonymous install telemetry and makes skills.sh list the repo.
6. Add the skills.sh badge to `README.md`, once it resolves (one-line PR).
7. Open the ComposioHQ/awesome-claude-skills PR.
8. Later, by date or star count: the heilcheng and VoltAgent PRs.

The founder does these in their own account:

- Submit to Anthropic's directory: answer the data-handling questions, the contact email and the acknowledgements.
- Fill in the awesome-claude-code web form, on or after 2026-11-03. That list only accepts submissions made by a person in the browser.
- Post on LinkedIn and X.

Delete this folder after launch (checklist step 17).
