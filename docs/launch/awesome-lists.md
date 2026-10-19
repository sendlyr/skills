# Awesome-list entries

These entries are ready to submit. Each one matches its list's own rules, which were read on 2026-10-20. Submit each one only after approval.

Most of these lists turn away brand-new repositories. This repo's first commit was on 2026-10-19 and it had 1 star at launch. The table shows when each list becomes realistic.

| List | Stars | Last merge seen | Rule that applies to us | Earliest date |
|---|---:|---|---|---|
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 77k | 2026-05-22 | No age or star rule. Over 1,000 open PRs, so merging is slow. | Launch day |
| [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | 56k | 2026-10-19 | 14 days old with commits after day one, **or** 100 stars. Web form only, filled in by a person. | 2026-11-03 |
| [heilcheng/awesome-agent-skills](https://github.com/heilcheng/awesome-agent-skills) | 6.3k | 2026-10-15 (weekly batches) | Older than 14 days **and** at least 20 stars. Otherwise the PR is put "on hold". | 2026-11-03, once at 20 stars |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | 36k | 2026-10-19 | "Brand new skills that were just created are not accepted." No number is given. | After real use: stars, forks, and issues or PRs from people outside Sendlyr |

Two more places list repos automatically, with nothing to submit:

- **skills.sh** lists a repo after its first `npx skills add sendlyr/skills` install. See [`skills-sh-badge.md`](skills-sh-badge.md).
- **[quemsah/awesome-claude-plugins](https://github.com/quemsah/awesome-claude-plugins)** is filled by a crawler that indexes repos with Claude Code plugins. Its README shows only the top 100 by stars.

These lists were skipped as inactive: travisvn/awesome-claude-skills (last merge 2026-01-07) and BehiSecc/awesome-claude-skills (last merge 2026-06-03).

---

## 1. ComposioHQ/awesome-claude-skills

**Rules** ([CONTRIBUTING.md](https://github.com/ComposioHQ/awesome-claude-skills/blob/master/CONTRIBUTING.md)): skills must solve a real problem, be documented, include examples and be tested. Entries go in a category, in alphabetical order. Use "no emojis, consistent punctuation". Recent merges only edit `README.md` and link to an external repo, using the `*By [@handle](...)*` suffix.

**Where:** `README.md`, section `### Business & Marketing`. Alphabetically, the entry goes last, after `Lead Research Assistant`.

**Line to add:**

```markdown
- [Sendlyr Lifecycle Measurement](https://github.com/sendlyr/skills) - Six skills that find the behaviour that predicts conversion, design lifecycle states and send rules, check AI-written emails for false claims, and prove results with a sealed holdout. *By [@sendlyr](https://github.com/sendlyr)*
```

**Branch:** `add-sendlyr-lifecycle-measurement`

**PR title:** `Add Sendlyr Lifecycle Measurement skills to Business & Marketing`

**PR body:**

```markdown
Adds one line to Business & Marketing for https://github.com/sendlyr/skills (MIT).

**What problem it solves:** Lifecycle email programs often report sends and opens, but nobody can tell whether anything changed. These six skills find the early behaviour that predicts conversion, send each user one ask based on how far they are from it, check AI-written emails for false claims, and measure the result with a pre-registered holdout that can say yes, no or "can't tell".

**Who uses this workflow:** growth, lifecycle and product analytics teams at trial and subscription products.

**Credit:** based on Sendlyr's lifecycle program with eReflect's Typesy in 2026. The real figures are published with permission in docs/lessons.md, including the experiment that showed nothing.

**Example:** "Use finding-leading-indicators on examples/practica and tell me what to track." The repo ships a synthetic dataset with an answer key, and every script is tested against it.

Works in Claude Code (plugin), on claude.ai (zip upload) and in any Agent Skills client. Scripts are standard-library Python with no network access.
```

---

## 2. hesreallyhim/awesome-claude-code

**Rules** ([CONTRIBUTING.md](https://github.com/hesreallyhim/awesome-claude-code/blob/main/CONTRIBUTING.md)):

- Submit through the web issue form only: <https://github.com/hesreallyhim/awesome-claude-code/issues/new?template=recommend-resource.yml>
- "Do not open a PR." Submitting with the `gh` CLI is not possible, and a person must fill in the form. Breaking these rules can get you restricted from the repo.
- The repo must be 14 days old with commits after the first day, or have 100 stars. The first commit was 2026-10-19 23:45 (+10:00), so the earliest date is **2026-11-03**.
- One resource at a time. Write descriptions, not a sales pitch. Don't address the reader. One line, no emojis.

**Form fields:**

| Field | Value |
|---|---|
| Display Name | `Sendlyr Skills` |
| Category | `Skills` |
| Link | `https://github.com/sendlyr/skills` |
| Author Name | `Sendlyr` |
| Author Link | `https://github.com/sendlyr` |
| Description (10–500 chars; this one is 376) | `A Claude Code plugin with six skills for measuring lifecycle email programs. It finds the early behaviour that predicts conversion, designs user states and send rules, checks AI-written emails for false claims, and runs holdout experiments with a pre-registered readout. Each skill ships a standard-library Python script, tested against a synthetic dataset with an answer key.` |

**Checklist:** tick the first five boxes only after you have done each one yourself, with your own eyes. **Leave the last box unchecked.** It is a trap: ticking it says you didn't read the form.

---

## 3. heilcheng/awesome-agent-skills

**Rules** ([AGENTS.md](https://github.com/heilcheng/awesome-agent-skills/blob/main/AGENTS.md), which applies to people and agents):

- Public GitHub repo with a `SKILL.md` that has `name` and `description`. We have six.
- **At least 20 stars, and not created in the last 14 days.** Otherwise the PR is labelled `on hold`. AGENTS.md says not to open a PR for a repo under 14 days old.
- Edit `README.md` only. Append one line to the end of an existing category under `## Community Skills`, inside its `<details>` block and before `</details>`. The diff must be purely additive.
- Format: `- [owner/repo](https://github.com/owner/repo) - Short description, under 100 characters, no marketing language`
- One open PR per repo. An automated check comments on the PR. Triage happens in weekly batches.

**Where:** the end of the `Marketing` block (after `chadboyda/agent-gtm-skills` on 2026-10-20). Don't use `Data & Analytics`: its `<details>` block isn't closed, so "the end" of it isn't well defined.

**Line to add (92 characters of description):**

```markdown
- [sendlyr/skills](https://github.com/sendlyr/skills) - Lifecycle email measurement: leading indicators, user states, claim checks, holdout readouts
```

**PR title:** `Add sendlyr/skills to Marketing`

**PR body** (their template, filled in):

```markdown
**Skill repository:** https://github.com/sendlyr/skills

**Category:** Marketing

### Checklist

- [x] The link is a public GitHub repository (or folder) that contains a `SKILL.md` with `name` and `description` frontmatter
- [x] The repository has at least 20 stars and is older than 14 days
- [x] I searched `README.md` and this repository is not already listed or in another open PR
- [x] I only edited `README.md`, adding at most 5 lines to the end of an existing category
- [x] Each line uses the format `- [owner/repo](https://github.com/...) - Description under 100 characters`
- [x] This is not a directory, marketplace, badge, or promotional link

### Disclosure

- [x] I am the author or a maintainer of this skill
- [ ] This PR was written by an AI agent (name it: ______ )
```

If Claude opens this PR, tick the last box and write `Claude Code`. Before ticking the stars box, check the star count on the day.

---

## 4. VoltAgent/awesome-agent-skills

**Rules** ([CONTRIBUTING.md](https://github.com/VoltAgent/awesome-agent-skills/blob/main/CONTRIBUTING.md)):

- Format: `- **[author/skill-name](https://github.com/author/repo/path)** - Short description of what it does`
- Description of **10 words or fewer**. The author or org prefix goes in the name.
- Community skills go at the end of the matching subcategory under "Community Skills".
- "Skill must have real community usage … Brand new skills that were just created are not accepted."
- PR title: `Add skill: author/skill-name`

**Where:** `README.md` → `### Community Skills` → `Marketing` (`<details>` block). Append just before its `</details>`. On 2026-10-20 the last entry was `publora/skills`.

**Line to add (9 words):**

```markdown
- **[sendlyr/skills](https://github.com/sendlyr/skills)** - Lifecycle measurement: leading indicators, user states, holdouts, honest readouts
```

**PR title:** `Add skill: sendlyr/skills`

**PR body:**

```markdown
Adds sendlyr/skills to Community Skills > Marketing.

Six MIT agent skills for lifecycle email measurement: finding the early behaviour that predicts conversion, designing user states and send rules, checking AI-written emails for false claims, and reading out holdout experiments. Each has a standard-library Python script, tested against a synthetic dataset with an answer key.

Usage: <stars, forks, and links to issues or PRs from outside users>
```

Don't submit this until you can fill in the usage line honestly. Leave out skills.sh install counts: they can be inflated, and our own test installs count too.
