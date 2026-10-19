# Anthropic plugin directory

How to list this repo in [Anthropic's directory](https://claude.ai/directory). After review, the listing appears in claude.ai chat, Cowork and Claude Code. The notes below come from Anthropic's docs as of 2026-10-20:

- [Publish to the directory](https://claude.com/docs/directory/publish)
- [Plugin pre-submission checklist](https://claude.com/docs/plugins/pre-submission-checklist)
- [Submit your plugin](https://claude.com/docs/plugins/submit)

The older Console form (`clau.de/plugin-directory-submission`) now redirects to these pages. It is no longer supported.

**Submit early.** A person at Anthropic reviews every new listing, and the review time isn't fixed. The repo is already public, so the submission doesn't have to wait for the release tag. The [checklist](checklist.md) puts it before launch day.

## Who can submit

- A claude.ai account on **Pro, Max, Team or Enterprise**. Free accounts can't submit. On Team or Enterprise, only an **Owner** can submit, or a member an Owner gave the **Directory** permission.
- **The listing belongs to the organization that submits it.** The first organization to submit `sendlyr/skills` holds the listing for good. Submit from the account or organization that should own it long term.
- **GitHub must be connected on claude.ai in that same organization**, and the GitHub account needs push access to `sendlyr/skills`. Setting up the push webhook needs admin access to the repo.
- Limits: 10 submissions per organization per 24 hours, and one submission per repo and folder.

## Pre-check of this repo (done 2026-10-20 on `main` @ 255d97b)

| Check | Result |
|---|---|
| `claude plugin validate --strict .` | ✔ Validation passed |
| `.claude-plugin/plugin.json` at repo root, `name` = `sendlyr` (lowercase, not reserved) | OK |
| `description`, `author`, `version` set | OK (`0.1.0`) |
| README at least 40 words; `LICENSE` file and `license` in plugin.json | OK |
| No `.DS_Store`, `Thumbs.db` or `__MACOSX` files | OK |
| Under 512 files; repo under 50 MiB | OK (97 files, 4.6 MB) |
| No hooks, no MCP servers, no `npx`/`uvx` launchers, no lockfiles | OK |
| No network calls in shipped code; scripts are stdlib Python | OK. Only the tests use `subprocess`, to run the scripts. |
| No binary files (`.zip`, `.pdf`, `.ico`) | OK. Don't commit the release zips. |
| Files under 256 KiB | **Policy hold expected.** Six CSVs in `examples/practica/` are 282 KiB–1.6 MiB (largest: `observational/events.csv`). |
| No symlinks | **Warning expected.** `CLAUDE.md` is a symlink to `AGENTS.md`. It is a warning only, because the plugin doesn't load it. |

The CSV hold doesn't block submission. A reviewer reads every new listing anyway. But the scan can raise the same hold **on every later version**, so each release may wait for a reviewer. The fix is to shrink the example CSVs below 256 KiB, or to move the plugin into a subfolder. Both touch the dataset and the tests, so they are a follow-up and not part of the launch.

The security scan reads the **whole repo**, including `docs/launch/`. These drafts contain shell commands (`curl`, `npx`, `gh`). They are documentation, not skill instructions. Still, removing `docs/launch/` after launch keeps the scanned payload clean. Every plugin install clones the whole repo, so the drafts would also ship to users.

## What to fill in

Portal: <https://claude.ai/directory/manage> → **Submit new** → **Plugin bundle**.

### 1. Source

| Field | Value |
|---|---|
| **Repository** | `sendlyr/skills` |
| **Plugin path (optional)** | leave empty (the plugin is at the repo root) |
| **Branch or tag (optional)** | leave empty to follow `main` |

Select **Validate**. Expect the CSV policy hold and the symlink warning above, and nothing that blocks. A result applies to one commit, so if anything is pushed to `main` afterwards, validate again.

**Tracking `main` vs a tag:** with `main`, every merge becomes a new version that gets scanned. That is fine as long as **auto-publish stays off** (see step 5): nothing goes live until you select **Publish**. A tag is stricter, but release tags shouldn't be moved, so `main` plus manual publishing is simpler.

### 2. Listing details

These are read from `plugin.json` and `README.md`, and they can't be edited in the form. Check how they look:

- The name shows as `sendlyr`. `plugin.json` has no `displayName`. Adding `"displayName": "Sendlyr"` (a one-line change to `.claude-plugin/plugin.json`) would show a nicer name. Optional, and it needs a push and a re-validate before submitting.
- The short description comes from `plugin.json` → `description`.
- The README becomes the listing's long description.

### 3. Data handling

The questions cover: does the plugin read or store personal data, does it send data to services other than its declared connectors, how long it keeps data, and is it meant for people under 18. The facts for answering them:

- **Reads personal data?** It reads only what the user gives it: CSV exports of accounts, events, assignments, outcomes and sends. These can contain pseudonymous user IDs. The scripts process them where the agent runs, and reports print aggregates only, never user IDs (`AGENTS.md`, `docs/data-contracts.md`). The safe answer is **yes, user-supplied event data, processed locally**, rather than "no".
- **Stores data?** Only report files, written to the `--out` folder the user chooses. Nothing is kept anywhere else.
- **Sends data to other services?** No. There are no network calls and no connectors.
- **Retention:** none by the plugin. The user's own report files stay where the user saved them.
- **Under 18?** No. It is a B2B analytics tool.

The founder must answer these. The text above lists facts, not legal advice.

### 4. Compliance

- **Contact email:** an address Anthropic can reach about the submission. The founder chooses it.
- **Acknowledgements:** four checkboxes. Read them first; they bind the organization to the [Software Directory Terms](https://support.claude.com/en/articles/13145338-anthropic-software-directory-terms) and [Software Directory Policy](https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy).

### 5. Review and submit

- **How new versions reach the directory:** **GitHub push webhook** (default; needs repo admin, then **Set up push updates**) or **Scheduled check only**. Both work. The webhook just picks up new commits sooner.
- **Auto-publish passing versions:** leave **off**, so each new version waits for you to select **Publish**.
- Select **Submit for review**.

## After submitting

- Review time isn't fixed. Track the status under **Submissions** in the portal.
- When a version passes, select **Publish**. By default an Anthropic reviewer then publishes it.
- Once the listing is live, raise `version` in `plugin.json` with every release.
- To stop it: **Withdraw submission** before it's published, or **Delist plugin** after.
- Stuck? Email `directory@anthropic.com`.

## Later changes that affect the listing

- **An MCP server or any package launcher** (`npx`, `uvx`, `bunx`, `pnpm dlx`, `pipx run`, `uv run`): pin every package to an exact version, for example `npx <package>@1.2.3` or `uvx <package>==1.2.3`. Unpinned launchers block. Pinned ones are still held for a reviewer. A remote MCP server should also be submitted on its own, as an **MCP connector**.
- **Hooks:** any `UserPromptSubmit`, `PreToolUse` or `PostToolUse` hook must be limited to projects that are relevant to the plugin. Any network call must be disclosed in the README, with a way to opt out.
- **Network calls in scripts:** describe them in the README. Today there are none, and the README says so.
- **Every release:** raise `version` in `plugin.json`, and tag the same version (`v0.2.0` ↔ `"version": "0.2.0"`).
