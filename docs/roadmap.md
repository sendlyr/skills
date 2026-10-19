# Roadmap: v2, organised around adoption stages

Status: **draft for discussion, 2026-10-20.** Nothing here has been built. Each section ends in proposals; [section 9](#9-decisions-needed) lists the decisions that are needed before building starts.

v1 (0.1.0) answers one question well: *what early behaviour predicts one outcome, and did driving it work?* v2 widens that to the whole lifecycle and to any team. It adds four things:

- the **stage** each customer is in;
- the **segment** they belong to;
- the **data tools** a team already uses;
- the **monitoring** a running test needs.

The measurement discipline stays the same.

**In short:**

- **Organising idea:** segment → stage → each segment's adoption point → drive toward it → prove it with a holdout → next stage (section 1).
- **Eleven new skills:**
  - analysis: stages, segments, hypotheses;
  - tracking: setup and audit;
  - monitoring: dashboards;
  - integrations: three read-only skills;
  - customer outcomes: emails, retention, happiness.
- **Extensions to five of the v1 six:** A/B/n tests, guardrails, channels, deliverability, fatigue (section 2).
- **Integrations compose with official vendor MCP servers** for definitions and aggregates. Row-level data moves through exports, disk to disk. Scripts stay offline (section 4).
- **Safety:** read-only by default, enforced by credentials. The agent never sends, launches or deletes. Writes come in a later phase, and only as a hashed, expiring plan of at most 20 operations, approved, applied once, read back, with a receipt and a revert plan (section 5).
- **Open source we can adapt** (actual LICENSE files read, and each file's lineage checked):
  - MIT: marketingskills, PostHog, GrowthBook, Amplitude's MIT repo, accoil, RudderStack;
  - Apache-2.0: Mixpanel, Anthropic's knowledge-work plugins;
  - ideas only: lenny-skills; nothing from repos without a licence (section 6).
- **Build order:** a foundations phase (facts file, macOS CI, offline harness, leak gate), then five feature phases of small PRs, each ending in a release (section 8). **Five decisions block Phase 1** (section 9).

---

## Contents

1. [The organising idea: adoption stages](#1-the-organising-idea-adoption-stages)
2. [The skills: what's new and how they chain](#2-the-skills-whats-new-and-how-they-chain)
3. [New data contracts and planted truths](#3-new-data-contracts-and-planted-truths)
4. [Integrations](#4-integrations)
5. [Safety model](#5-safety-model)
6. [What we adapt from open source, and under what licence](#6-what-we-adapt-from-open-source-and-under-what-licence)
7. [Gaps in the lifecycle stack](#7-gaps-in-the-lifecycle-stack)
8. [Build order](#8-build-order)
9. [Decisions needed](#9-decisions-needed)
10. [Not doing](#10-not-doing)
11. [Sources](#11-sources)

---

## 1. The organising idea: adoption stages

### The loop

```
  split into segments ──► pick a stage ──► find each segment's adoption point
        ▲                                             │  (predictive)
        │                                             ▼
  next stage ◄── decide ◄── read out the holdout ◄── drive customers toward it
   (new outcome,              (causal, or refuse)      (states → journeys → emails)
    new adoption point)
```

A customer moves through **stages**. Each stage has one outcome, such as paying after the trial, renewing, or referring a friend. Customers in different **segments** reach that outcome in different ways. So each segment has its own **adoption point**: the early action that tips them toward the outcome. We find it, drive customers toward it, and prove the effect with a holdout. Then the segment moves to the next stage, which has a new outcome and a new adoption point.

### Definitions

| Term | Meaning | Already in v1 as |
|---|---|---|
| **Stage** | A transition with one outcome contract: entry moment (the anchor), outcome, outcome window, decision window, unit (user, account or household), and the reader of the messages. | The outcome contract in `finding-leading-indicators` |
| **Segment** | A group defined **only by facts known at stage entry**: plan, persona, acquisition channel, company size, platform, region, or an onboarding-survey answer. Never by behaviour after entry. That behaviour is the candidate signal, and using it as a segment leaks the outcome. | Strata in `designing-holdout-experiments` |
| **Adoption point** | The earliest action inside the decision window, done by the reader, that separates who completes the stage from who doesn't, *for one segment*. Labelled predictive until a holdout says otherwise. | The leading indicator |
| **Drive** | State model by distance to the adoption point, one ask per state, contact policy, grounded emails. | `designing-lifecycle-states`, `designing-state-journeys`, `grounding-lifecycle-emails` |
| **Measure** | A sealed holdout or A/B test on the stage outcome, with the adoption point as the mechanism metric. | `designing-holdout-experiments`, `writing-decision-readouts` |
| **Next stage** | When a segment's stage is settled (adopted, or stopped for a recorded reason), work moves to the next stage for that segment. | New |

**Naming.** Public copy uses **adoption point** for the per-segment, per-stage indicator and keeps **leading indicator** as the technical term in existing skills. It drops the acronym "PAI", which past documents used for two different things. *(Decision D1.)*

### What changes for each stage

| Stage | Typical outcome metric | What the adoption point often looks like |
|---|---|---|
| Signup → activated | Activation rate | A setup step: connect data, invite a teammate, add a child, set a goal |
| Trial → paid | Trial-to-paid conversion rate | The setup step plus first value, inside the trial |
| Paid → retained or renewed | Retention or renewal rate | A habit: use on N distinct days or weeks, a recurring workflow set up |
| Retained → expanded | Expansion rate (seats, plan, annual) | Breadth: second use case, more seats active, hitting a limit |
| Loyal → advocate | Referral rate, review rate, promoter share | A moment of delight: a result shared, a goal reached |
| Lapsed or cancelled → won back | Win-back rate | A return trigger: a new feature that fixes their stated reason |

**Customer happiness is measured, not assumed.** NPS, CSAT and support signals become supporting signals inside stages and *guardrails* on every test (section 7).

### Rules this adds to the method

These extend the ten principles in [`method.md`](method.md).

11. **One stage at a time per segment, one primary outcome per stage.** A test that tries to move conversion and retention at once will answer neither.
12. **Segments are defined at entry.** "Users who completed 3 lessons" is a signal, not a segment.
13. **A segment earns its own adoption point only if the difference replicates.** It must hold out of time and survive Holm correction across every split tried. Otherwise it's a stratum. *Split the ask, not the sample* (lesson 12).
14. **A different adoption point usually means a different ask in the same state model, not a separate program.** Randomise within strata and pre-register the interaction.
15. **Pick the stage by leak × headroom × testability.** Ask three things: how many customers are lost there, how far below the ceiling the rate sits, and whether a test can reach δ within the time budget. A ceiling stage is a poor first target. Typesy VIP's ~77% trial conversion left little room to move.
16. **Guardrail the next stage.** A trial-to-paid win that hurts first renewal or happiness is not a win. Pre-register the next stage's outcome as a guardrail with its own, longer horizon.
17. **Moving to the next stage is a decision, recorded like any other.**

### Worked example: Typesy (customer 0)

*Labelled worked example. Only figures already published in [`lessons.md`](lessons.md) are used.*

| Stage | Segment | Adoption point | Where it stands |
|---|---|---|---|
| Trial → paid (7-day trial, auto-converts) | Homeschool families (the parent reads the email) | **Parent adds a child within 7 days.** Households that never added one converted at 4.0%, against 46.8% once they had | Predictive. The restart test registers it as the mechanism |
| Trial → paid | VIP individuals | "≥ 1 course in 4 days" was tried. In the randomised control arm it didn't predict conversion (75.5% vs 78.4%), and the ~77% baseline left little headroom | By rule 15, check whether first renewal has more headroom before pushing trial conversion harder for VIP |
| Paid → renewal | Both | Not yet measured | The next stage. Its metric is the renewal or retention rate |
| Renewal → referral or engagement | Both | Depends on product direction | Later |

The same machinery serves every row. Only the outcome contract, the segment and the reader change.

---

## 2. The skills: what's new and how they chain

### The chain

```
 connect (read-only) ─────────────────────────────────────────────────────────────────┐
   connecting-product-analytics · connecting-data-warehouses · connecting-email-platforms
                                                                                       │ contract CSVs
 planning-product-tracking ──► mapping-adoption-stages ──► splitting-customer-segments │
   (is the data there?)          (which stage leaks?)        (which segments differ?)  │
                                          │                          │                 │
                                          ▼                          ▼                 │
                                 finding-leading-indicators  (adoption point per segment × stage)
                                          │
                                          ▼
                                 forming-lifecycle-hypotheses  (ranked, testable, sealed-ready)
                                          │
              ┌───────────────────────────┼─────────────────────────────┐
              ▼                           ▼                             ▼
   designing-lifecycle-states ─► designing-state-journeys ─► writing-lifecycle-emails
                                          │
                                          ▼
          designing-holdout-experiments (holdout or A/B) ──► building-monitoring-dashboards
                                          │                     (health, not verdicts)
                                          ▼
                              writing-decision-readouts ──► decision ──► next hypothesis or next stage

   Supporting outcomes and guardrails: analyzing-retention-cohorts · measuring-customer-happiness
```

### New skills

Each is a self-contained folder with SKILL.md, one stdlib script, references, assets and evals, like the v1 six.

| Skill | The question it answers | Script (stdlib) | In → out | Phase |
|---|---|---|---|---|
| `mapping-adoption-stages` | "Where in the lifecycle do we lose people, for whom, and which stage should we work on?" | `adoption_map.py` | `stages.toml` + wide `accounts.csv` → stage × segment grid: entered, mature, rate + Wilson CI, time to transition, customers lost, ceiling and maturity flags, weeks to power δ, recommended next cell; optional weekly aggregate series for dashboards | 1 |
| `splitting-customer-segments` | "Do our segments need different adoption points, or just different base rates?" | `segment_split.py` | candidate split columns (entry facts only) + events → per split: sizes, base rates, each segment's top adoption point, an interaction test, out-of-time replication, Holm across splits. Verdicts: `SAME_ADOPTION_POINT`, `DIFFERENT_ADOPTION_POINT`, `BASE_RATE_ONLY`, `TOO_SMALL` | 1 |
| `forming-lifecycle-hypotheses` | "What should we test next, and is it testable?" | `hypotheses.py` | adoption map, indicator cards, qualitative notes, past decision records → `hypotheses.toml` checked and ranked. Flags: no δ, no mechanism, untestable in the time budget, post-hoc, duplicate, already falsified, overlapping tests on the same segment and stage | 3 |
| `planning-product-tracking` | "Do we track what we need? Set it up, then audit it." | `tracking_audit.py` | stage contracts → `tracking-plan.toml` (events, actor, entry attributes, identity, naming, banned PII properties) + SDK snippets; then plan vs observed **daily event counts** → missing or unplanned events, volume drops, outcome events in the behaviour stream, missing actor, PII-shaped properties, late arrivals | 2 |
| `building-monitoring-dashboards` | "Is the test healthy? Is the adoption point moving?" | `dashboard.py` | `result.json` files + aggregate series → one self-contained `dashboard.html` (inline CSS and SVG, no JavaScript libraries, no network). It shows test health (assignment, SRM, reach, contamination, missing outcomes, countdown to analysis) and adoption points by cohort with CIs. **The arm difference stays hidden until `analysis_not_before`** | 3 |
| `connecting-product-analytics` | "Pull our PostHog / Amplitude / Mixpanel / Segment data without leaving the agent." | `analytics_bridge.py` | vendor export files (row level) and MCP reads (definitions) → `events.csv`, `accounts.csv`, `assignments.csv` (from experiment exposures), `tracking-plan.toml`; optional ID pseudonymisation; PII refusal | 2 |
| `connecting-data-warehouses` | "Build the contract files from Postgres / BigQuery / Snowflake and our billing system." | `extract_sql.py` | `stages.toml` → dialect SQL for every contract file, with aggregate-in-warehouse variants; `check` mode validates any extracted CSV against the contract and scans for PII | 2 |
| `connecting-email-platforms` | "What did Braze / Customer.io / SendGrid / Iterable / Klaviyo actually do?" | `esp_bridge.py` | platform exports → `sends.csv`; live campaign config → **policy drift report** against `contact-policy.toml` (lesson 9: the design said 3 emails, the live cap was 5); live templates → `emails.json` for `claim_check.py` | 2 |
| `writing-lifecycle-emails` | "Write the email for this stage and state, and make sure it's true." | `claim_check.py` (moved, extended) | craft adapted from marketingskills `emails` (MIT, credited) + the v1 grounding pipeline + per-stage playbooks: trial, trial ending, first renewal, payment failed, win-back, referral ask, survey ask | 4 |
| `analyzing-retention-cohorts` | "When and why do paying customers leave, by segment?" | `retention.py` | `subscriptions.csv` → Kaplan–Meier curves with Greenwood CIs (censoring done right: *blank is not no*), renewal rate per renewal point for mature cohorts, log-rank by segment, churn timing, voluntary vs involuntary split | 4 |
| `measuring-customer-happiness` | "Are customers happy, and does it predict renewal?" | `happiness.py` | `responses.csv` (+ optional population facts) → NPS, CSAT and CES with CIs by segment and stage, response rate, non-response bias check, trend; detractor and promoter flags as candidate signals for `finding-leading-indicators` | 4 |

With all of them, v2 has 17 skills: the v1 six plus eleven new ones. It has 16 if `writing-lifecycle-emails` replaces `grounding-lifecycle-emails`. *(Decisions D2, D3, D4.)*

### Extensions to the v1 six

| Skill | Extension | Phase |
|---|---|---|
| `finding-leading-indicators` | Read the wide `accounts.csv` from `stages.toml` (`--stages F --stage NAME`), so one export serves every stage. Add a **time-to-adoption-point** table (of those who reach it, the share who do so by day 1, 2, 3 …), which tells journeys when to ask. | 1 |
| `designing-holdout-experiments` | **A/B/n tests**, not just holdouts. Sizing for k arms (Holm-adjusted) and for mean metrics such as revenue per user. Pre-registered **guardrails** with non-inferiority margins. A global long-term holdout pattern. Reading exposures from GrowthBook, Statsig, PostHog or LaunchDarkly into `assignments.csv`. *(Decision D5.)* | 3 |
| `writing-decision-readouts` | k arms, each against control, Holm-adjusted. Mean metrics (Welch interval). Guardrail gate: a breached guardrail blocks "adopt" in the decision record without relabelling the primary class. The platform's own result is shown as "platform view" and never replaces the sealed readout. | 3 |
| `designing-state-journeys` | A `channel` column (email, push, in-app, SMS) with per-channel and total caps. A `program` column for cross-program contact pressure. **Deliverability and fatigue**: bounce, complaint and unsubscribe rates by state, message and program, and unsubscribe rate by recent contact pressure (predictive only). | 4 |
| `designing-lifecycle-states` | Optional `segment` in state rules, so one model can ask different segments for different adoption points (rule 14). | 1 |

The skills shared by every stage don't fork per stage. A new stage is a new `stages.toml` entry, not a new skill.

### How every skill is written

These rules apply to new skills and to edits of the v1 six.

- **Code computes every number; the skill carries the judgement.** A `SKILL.md` never asks the model to calculate a rate, an interval or a sample size. It says which script to run, how to read the result, and **what never to claim**. Unknown stays unknown and is never shown as zero.
- **Every threshold has a source label.** There are four kinds:
  - **lesson** (e.g. the 90% reach gate, lesson 1);
  - **vendor rule** (e.g. Gmail's 0.3% spam-rate ceiling);
  - **statistical convention** (e.g. α = 0.05);
  - **borrowed**.

  Borrowed thresholds are mostly folklore, such as "40% very disappointed" or "3% monthly churn is good". They ship only as a **starting band, labelled with their source**, which the user confirms for their own data. Every threshold is a flag or config value, never a hard-coded rule.
- **A no-credentials demo.** Each skill runs end to end on Practica and on the vendor replay bundles, in about a minute and with no accounts. The same files are its eval fixtures.
- **Typesy appears only as a labelled worked example.** No skill has Typesy-specific fields.

---

## 3. New data contracts and planted truths

Contracts are added to [`data-contracts.md`](data-contracts.md) **before** each script, as the repo already requires. Everything stays backward compatible: v1 files keep working, and new columns are optional.

### `stages.toml` (new; sketch)

```toml
[model]
name = "practica_lifecycle_v1"
unit = "user"                         # user | account | household: also the randomisation unit

[[segments]]                          # facts known at stage entry only
name = "family"
when = 'plan == "family"'             # the existing condition language
reader = "parent"                     # overrides the stage's reader for this segment

[[segments]]
name = "solo"
when = 'plan == "solo"'

[[stages]]
name = "trial_to_paid"
entered_at = "trial_started_at"       # a column in the wide accounts.csv
outcome_at = "paid_at"
outcome_window_days = 14
decision_window_days = 7
reader = "learner"
metric_label = "trial-to-paid conversion"

[[stages]]
name = "paid_to_renewed"
entered_at = "paid_at"
outcome_at = "renewed_at"
outcome_window_days = 45
decision_window_days = 30
reader = "learner"
metric_label = "first renewal rate"
guardrail_for = "trial_to_paid"       # rule 16
```

### Other additions (sketch)

| File | Change |
|---|---|
| `accounts.csv` | **Wide form** allowed: one timestamp column per stage boundary plus entry-fact columns, read through `stages.toml`. The v1 `anchor_at`/`outcome_at` form still works |
| `sends.csv` | Optional `channel`, `program`; statuses `bounced`, `complained`, `unsubscribed` |
| `prereg.toml` | Optional `[[arms]]`, `[primary] type = "binary" \| "mean"`, `[[guardrails]]` with `max_harm` |
| `hypotheses.toml` | New: id, version, segment, stage, intervention, mechanism metric and δ, outcome metric and δ, evidence (each tagged predictive, qualitative or prior test), guardrails, cost, created date, supersedes |
| `tracking-plan.toml` | New: events (name, actor, required properties, stage role), entry attributes, identity rules, naming rule, banned properties |
| `event-counts.csv` | New aggregate input: date, event, actor, count, distinct accounts. Lets the tracking audit run without raw rows |
| `subscriptions.csv` | New: account, started, ended, end reason (voluntary, involuntary, other), plan, observed until |
| `responses.csv` | New: respondent, asked at, responded at (blank = no response), score, survey type, segment, stage |
| `series.csv` | New aggregate output of `adoption_map.py`: cohort week, segment, stage, entered, hit adoption point, outcome measured, outcome hit. Dashboards read only this and `result.json` files |

New statistics, each defined once in the contracts: Kaplan–Meier with Greenwood intervals, the log-rank test, an NPS interval (the multinomial variance of promoter share minus detractor share), a Welch interval for differences of means, and a difference-of-lifts interval for the segment interaction test.

### Practica v2: new planted truths

New datasets go in **new folders** and use their own seeded RNG streams, so every existing file and answer is unchanged and the 136 current tests keep passing.

**Size budget: every new example file stays under 256 KiB.** The launch work ([PR 1](https://github.com/sendlyr/skills/pull/1)) reports that Anthropic's plugin directory puts a policy hold on any plugin file over 256 KiB. That is not yet verified here; confirm it before acting on it. Six existing Practica files are already over the limit, between 282 KiB and 1.7 MiB. Shrinking them is a separate small PR *(Decision D14)*.

| Folder | Planted truth | Tested by |
|---|---|---|
| `lifecycle/` | Two segments with **different trial adoption points**: `solo` = `goal_set` (as today); `family` = `member_invited`, a parent action that mirrors "adds a child". The **same renewal adoption point** for both: practised on ≥ 3 distinct days in the first 14 paid days. A `channel` split with a different base rate but the same adoption point. A tiny `edu` plan, too small to test. A post-entry attribute as bait. A referral-channel segment at a ~80% ceiling | `adoption_map.py`, `segment_split.py`, `score_signals.py --stages` |
| `retention/` | Censored recent payers; a cliff at first renewal; 30% of churn involuntary (failed payments); segments that differ by log-rank | `retention.py` |
| `happiness/` | Happier users respond more (non-response bias); detractors renew less (predictive only) | `happiness.py` |
| `tracking/` | A planned event that is never sent, an unplanned event, a 3-day volume outage, the outcome event in the behaviour stream, a missing actor, an email address in a property | `tracking_audit.py` |
| `hypotheses/` | One sound hypothesis, plus one each with: no δ, untestable in budget, post-hoc, duplicate | `hypotheses.py` |
| `ab-test/` | Three arms: B wins the primary but breaches the unsubscribe guardrail; C is inconclusive | `holdout.py`, `readout.py` |
| `vendor-exports/` | Synthetic files in each vendor's documented export shape; a live campaign config with cap drift (3 → 5) and a missing exit rule | `esp_bridge.py`, `analytics_bridge.py` |

---

## 4. Integrations

The founder wants teams to stop switching between sites. The research says to do that by **composing with the vendors' official MCP servers**, not by writing API clients. Section 4.3 has the vendor-by-vendor detail. Everything there was checked against vendor docs on 2026-10-20, and anything that couldn't be confirmed is marked.

### 4.1 The pattern: two paths, and the scripts stay offline

The most important research finding: **no MCP server is a bulk export path.** Results come back into the model's context, and they are capped:

- PostHog `execute-sql`: 50k rows;
- BigQuery managed MCP: 3,000 rows;
- Snowflake managed MCP: 250 KB.

Row-level data sent through MCP also puts user IDs into the conversation. Braze's MCP returns no user-level data at all. So every connecting skill uses two paths:

| Path | Used for | How |
|---|---|---|
| **MCP, read-only** | Discovery and definitions: schemas, event lists, campaign and journey configs, caps, segments, tracking plans, experiment settings. Aggregate checks: counts, dry runs, SRM | The vendor's official server, connected by the user with read-only credentials (section 5) |
| **Export to disk** | Row-level contract files: `events.csv`, `accounts.csv`, `sends.csv`, `assignments.csv`, `subscriptions.csv`, `responses.csv` | The vendor's CLI or export API writes straight to a file. Examples: `psql \copy`, `bq query --format=csv --maximum_bytes_billed`, `snow sql --format CSV`, Braze Currents, the Amplitude or Mixpanel export API. The human runs it, or approves the exact command. The rows never pass through the chat |

Then a `*_bridge.py` script, which is offline and stdlib-only, converts the vendor's file into the contract format. It:

- maps vendor statuses to ours;
- pseudonymises IDs with a salt the user keeps;
- drops every property the contract doesn't need;
- refuses to write a file that still contains email addresses, phone numbers or IPs.

The analysis scripts then run as they do today. **No script opens a network connection or takes a credential, in v1 or v2.** A test will enforce that.

### 4.2 What each connecting skill does

| Skill | Reads through MCP | Exports to disk | Bridge output |
|---|---|---|---|
| `connecting-email-platforms` | Campaign, canvas, flow and journey definitions; frequency caps; control groups; templates; aggregate send series | Send logs (Braze Currents; Customer.io deliveries; SendGrid Email Logs or Event Webhook; Iterable export; Klaviyo "Received Email" events) | `sends.csv`. A **policy drift report** of the live config against the sealed `contact-policy.toml`. Live templates as `emails.json` for `claim_check.py` |
| `connecting-product-analytics` | Event and property definitions, tracking plans (Avo, RudderStack, Snowplow, PostHog, Amplitude, Mixpanel), experiment and flag settings, aggregate counts | Event exports (warehouse, or the Amplitude, Mixpanel or PostHog export); experiment exposures (GrowthBook, Statsig, LaunchDarkly, Optimizely, PostHog) | `events.csv`, `accounts.csv`, `assignments.csv`, `tracking-plan.toml`, `event-counts.csv` |
| `connecting-data-warehouses` | Schemas, dry runs and cost estimates, aggregate sanity checks | Contract files through each warehouse's CLI. Billing outcomes from Stripe, RevenueCat, Chargebee or Paddle exports | SQL per dialect, generated from `stages.toml`. `check` mode validates any extract |

Each connecting skill also ships:

- **`setup` and `doctor` steps.** `setup` walks the user through connecting the vendor's official server with read-only credentials. `doctor` proves access with **one real read** and prints the exact fix when it fails: the missing scope, the wrong region host, the plan tier. Scripts stay offline, so the agent makes that one MCP read, and the bridge's own `doctor` mode checks the exported file offline.
- **A capabilities matrix per vendor** (`assets/vendors.toml`): what it can read, through which path, its rate limits, and what it **can't** expose. Examples: Braze's MCP has no user-level sends; SendGrid has no frequency caps or holdouts. The skill never claims to read something that isn't in the matrix. Tests check that every vendor entry has its limits and the date it was checked.
- **A recommended Claude Code permission file per vendor.** It allows the named read tools, asks on anything else, and denies the known send, launch and delete tools. Claude Code evaluates deny, then ask, then allow, and an allow rule can't override a deny.
- **One reference file per vendor**: setup, the read-only lever, the export recipe, the status mapping, known traps, and the date the docs were last checked. Vendor docs change, so each file carries that date.
- **Example MCP configs, never enabled by default.** For Codex, add `.codex-plugin/plugin.json` and an `mcp.json` example with an explicit transport `type`. The plugin itself installs skills only; it doesn't silently add vendor servers.

Where a vendor already ships an official agent plugin, our skill points to it rather than duplicating it. Customer.io's Claude plugin (MIT) is one example. Our skill adds only the contract mapping and the measurement checks.

### 4.3 Vendor reference (checked 2026-10-20)

"Read-only lever" is the strongest control the vendor offers. "Never without a human" lists example tools that a skill must never call on its own.

**Email and messaging platforms**

| Vendor | Official MCP | Read-only lever | Row-level path | Never without a human |
|---|---|---|---|---|
| Braze | Yes. Hosted [`mcp.braze.com/mcp`](https://www.braze.com/docs/user_guide/brazeai/mcp_server/) (EU `mcp.braze.eu`), GA in the 2026-09-17 [release notes](https://www.braze.com/docs/releases/2026/9_17_26). The old local server is deprecated | **None on the server.** The agent gets the signed-in user's permissions, so use a low-permission dashboard user plus client deny rules. Braze advises against auto mode ([setup](https://www.braze.com/docs/user_guide/brazeai/mcp_server/setup/)) | [Currents](https://www.braze.com/docs/user_guide/data/distribution/braze_currents/event_glossary/message_engagement_events/) Send/Delivery/Bounce/Abort events. Not through MCP, which returns no user-level data. Depends on the Braze package | `launch_campaign`, `stop_campaign`, `edit_campaign`, `create_segment` ([tools](https://www.braze.com/docs/user_guide/brazeai/mcp_server/available_api_functions/)) |
| Customer.io | Yes. Hosted [`mcp.customer.io/mcp`](https://docs.customer.io/ai/mcp-server) (EU host too). Official [Claude plugin](https://github.com/customerio/claude-plugin), MIT | OAuth `read` scope is the default. `write`, `write:live` (sends) and `configure` are separate. CLI service tokens can be permanently read-only | `GET /v1/messages` (6 months), the deliveries export, or warehouse sync (Premium and Enterprise plans) | `cio_write_api`, `cio_delete_api`, anything under `write:live` |
| SendGrid | **No account-level MCP.** Twilio's [MCP](https://www.twilio.com/docs/ai/mcp) searches docs only | A Custom Access API key ([keys](https://www.twilio.com/docs/sendgrid/ui/account-and-settings/api-keys)) | [Email Logs API](https://www.twilio.com/docs/sendgrid/api-reference/email-logs) (30 days); [Event Webhook](https://www.twilio.com/docs/sendgrid/for-developers/tracking-events/event) (put the message key in `custom_args`); Email Activity (paid add-on) | Single Sends with `send_at: "now"`; creating webhooks |
| Iterable | Yes, **beta**. Local [`@iterable/mcp`](https://github.com/Iterable/mcp-server), MIT | **Read-only is the default mode, enforced by the server** (no PII, writes or sends) | [Export API](https://support.iterable.com/hc/en-us/articles/204780579): `emailSend`, `emailSendSkip`, `emailBounce`. The MCP export needs both the PII and writes flags, so the human runs it | `send_campaign`, `trigger_campaign`, `trigger_journey`, `start_experiment`, `declare_experiment_winner` ([tools](https://github.com/Iterable/mcp-server/blob/main/TOOLS.md)) |
| Klaviyo | Yes. Hosted [`mcp.klaviyo.com/mcp`](https://developers.klaviyo.com/en/docs/klaviyo_mcp_server), GA since 2025-08 | `?read-only=true` and `toolsets=…:read` on the remote URL; `READ_ONLY=true` locally; Read-Only keys ([connect](https://developers.klaviyo.com/en/docs/connect_to_the_klaviyo_mcp_server)) | Events API filtered to "Received Email". The bulk export is an invite-only beta | `send_campaign`, `update_flow` (status), `bulk_suppress_profiles`, `merge_profiles` |
| HubSpot, Postmark, Mailchimp Transactional | Yes (hosted, local and hosted respectively) | None on the server. Use low-permission users or keys plus deny rules | Not researched in depth | Postmark `sendBatch` (500 per call), Mandrill `call_api` |

Experiment features worth mapping in `references/`:

- **Braze:** a global control group, campaign and Canvas control groups, frequency-cap rules, and quiet hours (held messages all send at once when the window ends).
- **Customer.io:** holdouts through random-cohort branches.
- **Iterable:** experiment holdouts and send-skip reasons.
- **Klaviyo:** a global holdout (needs a large audience) and Smart Sending.
- **SendGrid:** no holdout or frequency-cap features were found.

**Product analytics, tracking plans and experimentation**

| Vendor | Official MCP | Read-only lever | Row-level path | Never without a human |
|---|---|---|---|---|
| PostHog | Yes. Hosted [`mcp.posthog.com/mcp`](https://posthog.com/docs/model-context-protocol) (the README names an EU host). Source in the MIT monorepo | `?readonly=true`, `?tools=`, project pinning, a scoped personal key | `execute-sql` (50k-row cap), or batch export to a warehouse | Flag rollout or enable, `experiment-launch/end/ship-variant`, `persons-bulk-delete` |
| Amplitude | Yes. Hosted `mcp.amplitude.com/mcp` | An RBAC role with only "Use MCP (read)" | Export API `/api/2/export` (zipped JSONL) | Experiment and flag create or update, taxonomy writes |
| Mixpanel | Yes. Hosted [`mcp.mixpanel.com/mcp`](https://mixpanel.com/ai/mcp) | **No read-only mode**, as Mixpanel's own page says. Use a client allowlist | Raw Export API (JSONL, 60 requests per hour) | `Edit-Event`, `Bulk-Edit-*`, feature-flag writes, `Delete-Dashboard` |
| Segment | **No official MCP for workspace data.** Use the Public API | Public API token; Protocols plan needed for tracking plans | Warehouse `tracks` tables | `PUT …/rules` (full replace); Block Event, which discards events permanently |
| Avo | Yes. Hosted `mcp.avo.app/mcp` (beta) | `read` scope by default. `write` needs a browser re-auth; writes go to branches and a human merges | Schemas only | `save_items` (some changes apply immediately) |
| RudderStack, Snowplow | Yes (hosted; Snowplow also has a local CLI) | Allowlist the read tools; a Snowplow View key or `--read-only` | Warehouse tables | `rudder-cli apply` (deletes what isn't in the project), Snowplow `dp purge` |
| GrowthBook | Yes. Hosted and local, [MIT](https://github.com/growthbook/growthbook-mcp) | A Read Only role key; per-key "Require confirmation" (a real human gate) | The experiment assignment query in the warehouse | Feature toggles, experiment start or stop |
| Statsig | Yes. Hosted V3 (beta) | The key of a read-only role user. Its `confirmation` field is filled in by the agent, so **it is not human approval** | `first_exposures` report, warehouse export | `gate_update`, `experiment_update` |
| LaunchDarkly, Optimizely, Datadog Experiments (formerly Eppo) | Yes (hosted; LaunchDarkly also local, MIT) | Reader or Viewer roles. LaunchDarkly says its URL parameters "don't limit what the connection can do" | Data Export add-on, Events Export, warehouse exposure tables | `toggle-flag`, `update-rollout`, experiment lifecycle tools |

**Warehouses and databases**

| Vendor | Official MCP | Read-only lever | Row-level path |
|---|---|---|---|
| Postgres | No single vendor server. **Never use the archived reference server**: its read-only transaction can be escaped with `COMMIT;`, and the npm package was never patched ([Datadog Security Labs](https://securitylabs.datadoghq.com/articles/mcp-vulnerability-case-study-SQL-injection-in-the-postgresql-mcp-server/)) | A SELECT-only role, `default_transaction_read_only`, `statement_timeout`, a replica | `psql \copy (…) TO 'x.csv' CSV HEADER` |
| BigQuery | Google-managed remote MCP | `execute_sql_readonly`, an IAM deny on non-read-only tools, dry runs. `LIMIT` does not cap bytes scanned; Google's [MCP Toolbox](https://github.com/googleapis/mcp-toolbox) (Apache-2.0) adds `maximumBytesBilled` | `bq query --format=csv --maximum_bytes_billed=…` |
| Snowflake | Snowflake-managed MCP (GA 2025-11). `Snowflake-Labs/mcp` was **deprecated 2026-05-15** | `SYSTEM_EXECUTE_SQL` is read-only by default; a USAGE+SELECT role; query timeouts (the default is 2 days); budgets | `snow sql --format CSV` |
| Supabase, Neon | Yes (hosted) | `read_only=true` or `readonly=true`, plus a restricted role (the token itself can still write) | `psql \copy` |
| ClickHouse, Databricks, MotherDuck | Yes | `readonly=1` by default; a `disallow_writes` policy; read-only by default | Each vendor's CLI writes the file to disk |

**Subscription billing** (the source of truth for trial → paid, renewal and churn)

| Vendor | Official MCP | Read-only lever | Row-level path | Never without a human |
|---|---|---|---|---|
| Stripe | Yes. Hosted [`mcp.stripe.com`](https://docs.stripe.com/mcp), [stripe/ai](https://github.com/stripe/ai) MIT | A restricted, agent-tagged key with per-resource Read. **Stripe stops accepting full-access and untagged keys from December 2026** | `GET /v1/subscriptions?status=all` (the default leaves out cancelled subscriptions). Events go back only 30 days, so use Sigma or Data Pipeline for history | `stripe_api_write` (refunds, cancelling or updating subscriptions, invoices, coupons), `send_money` |
| RevenueCat | Yes. Hosted | `:read` keys; the server hides tools you have no permission for | Scheduled Data Exports. They include user IDs and IPs, so pseudonymise them | `grant-customer-entitlement`, `publish-paywall`, experiment start or stop |
| Chargebee | Yes. Hosted per site (Data Lookup) | Enable only the read toolsets; Read-only site keys | The Export Subscriptions API | The export tools create jobs |
| Paddle | Yes. Hosted `mcp.paddle.com/mcp` | `entity.read` keys. The remote server **does not gate destructive operations**, and the legacy local server's default mode can still move money (use `--tools=read-only`) | `GET /subscriptions`; events are kept 90 days; Reports CSV | `execute`, `cancel_subscription`, `create_subscription_charge` |
| Recurly | Docs-only MCP | **None**: API keys have full access | Automated Exports | — |

**Customer feedback** (for `measuring-customer-happiness`)

| Vendor | Official MCP | Read-only lever | Row-level path |
|---|---|---|---|
| Intercom | Yes. Hosted | A read-only app token | REST conversation search on `conversation_rating` (CSAT) |
| Zendesk | None shipped yet (announced) | OAuth `satisfaction_ratings:read`. API tokens stop working on 2027-04-30 | Satisfaction ratings and survey responses APIs |
| Typeform | Yes. Hosted | **Can't be read-only over MCP**, because it requires every scope. Use REST with `responses:read` instead | `GET /forms/{id}/responses` |
| SurveyMonkey | Yes. Hosted (tools not verified) | REST `responses_read_detail` | Bulk responses API |
| Delighted | **Sunset June 2026.** Leave it out | — | — |

**Not verified** (to check during the build):

- **Braze:** whether a view-only Braze user gives a clean read-only MCP, and whether frequency-cap rules can be read through the API.
- **Customer.io:** whether it has a global control group.
- **Iterable:** export rate limits.
- **Klaviyo:** which property names carry the message ID.
- **PostHog:** whether its MCP key preset is read-only.
- **SurveyMonkey:** its tool names.

---

## 5. Safety model

The rule stays the v1 rule: **the agent proposes, the human approves.** Connecting to live systems adds three risks:

- actions that can't be undone;
- personal data entering the conversation;
- instructions hidden in customer data.

The model below addresses each one.

### 5.1 Four tiers of action

| Tier | What | Examples | Who acts | Guard |
|---|---|---|---|---|
| **0. Offline** | Scripts on local files | Every analysis script | Agent | No network, no credentials, aggregates only (as in v1) |
| **1. Read** | Read-only calls through an official MCP server; export commands that write to disk | List campaigns and caps, read a tracking plan, dry-run a query, count events, export send logs to a file | Agent, once the human has connected the server with read-only credentials | Read-only credentials and roles (5.3), bounded queries, row-level data written to disk only |
| **2. Propose, then apply on approval** | A **change plan** file (a diff), a human yes for that one change in the moment, apply exactly that change, verify it, log it | Add an event to a tracking plan (on a branch, where the vendor supports it), create a *draft* template from approved email JSON, create a flag at 0% or an inactive experiment, define a segment | The human approves the plan's hash. The agent applies it once | The approval protocol in 5.2. Never while a sealed test is running, because that's a protocol deviation. **Not in 0.x** *(D8)* |
| **3. Never by the agent** | Anything that reaches customers, moves money or destroys data | Send, schedule, launch, activate or resume a campaign or flow; change a live audience or a running test's allocation; declare a winner; refunds, cancellations, charges; delete or merge profiles; change suppression or unsubscribe lists; create webhooks or standing exports; create or rotate credentials | A person, in the vendor's own UI | The skills never instruct it. The permission files deny the known tools *(D7)* |

### 5.2 How a Tier 2 change is approved

Writes are never direct. This protocol was learned by a team that open-sourced an ads MCP server and skills. A small stdlib script, `change_plan.py`, enforces its mechanics offline, so the rules are code and not memory:

1. **Plan.** The agent writes a change plan: the vendor, each operation, the current value read back, the new value, and how to revert it. **At most 20 operations.** Anything larger needs a separate review step.
2. **Hash.** The script hashes the plan and shows the human the plan with its hash.
3. **Approve.** The human's explicit "yes" is pinned to that hash. A changed plan needs a new yes. Silence, an earlier yes, or a refusal in chat never counts. Plans expire after **30 minutes**.
4. **Apply once.** The agent applies exactly the approved operations, once.
5. **Read back.** The agent re-reads each changed object, and the script compares the values with the plan.
6. **Receipt.** The script writes a receipt: the hash, the time, the operations, the read-back result and the revert plan. It holds no IDs beyond the vendor's object IDs, and no customer data.
7. **Revert.** Every receipt carries a ready revert plan, which goes through the same protocol.

### 5.3 Read-only is enforced by credentials, not by trust

URL flags and tool annotations are hints. Read-only has to be enforced where the vendor's own boundary is. Each case from the research shows why:

- The MCP spec treats annotations from untrusted servers as untrusted.
- LaunchDarkly says its URL parameters "don't limit what the connection can do".
- Snowflake says annotations are client-facing hints, not security controls.
- The old Postgres server's read-only transaction could be escaped.

So each vendor reference file names the strongest lever that vendor has, in this order:

1. **The server removes write tools.** Iterable's default mode; Klaviyo `read-only=true`; PostHog `readonly=true`; Supabase or Neon read-only.
2. **The credential can only read.** Read-only keys and scopes, SELECT-only database roles, Viewer or Reader app roles.
3. **A low-permission user**, where nothing else exists (Braze, HubSpot, Mixpanel).
4. **Always also:** the shipped permission file, which denies the known Tier 3 tools and asks on everything not on the read list. It is written for Claude Code, with notes for other agent clients.

Two traps get their own warning:

- **Read-only keys sometimes can't export.** A Customer.io read-only token allows GET only, and its delivery export is a POST. Iterable's read-only key excludes the export endpoints. The fix is **never to widen the agent's key.** The human runs the export, or approves the exact export command.
- **Some "confirmations" are filled in by the agent itself.** Statsig's `confirmation` field is one. Only gates a person clicks count as approval: GrowthBook's "Require confirmation", Stripe's confirmation link, Avo's re-auth and human merge, and the agent client's own permission prompt.

### 5.4 Personal data stays on disk

- Row-level data moves **disk to disk**: from the vendor's CLI or export into a file, then through a bridge script into a contract file. The agent reads only the aggregate `report.md` and `result.json`.
- Bridges pseudonymise IDs with a salt from the user's environment. They refuse to write output that still holds email addresses, phone numbers, IPs or free-text names.
- **The redactor is tested by round-trip.** Every stored payload must survive it unchanged, apart from the intended fields. Another team's redactor silently erased every field whose name ended in `_key` or `_token`. Our contract has `message_key`, so a test pins it.
- Warehouse access should go through a **pseudonymised view** in a separate read-only schema, not the raw tables. The SQL templates create that view as a human-run step.
- Reports never print user IDs. That rule is unchanged, and the tests extend to every new script.
- Exports carry a retention note: delete them when the analysis is done.

### 5.5 Credentials stay in the user's environment

- **Users bring their own credentials.** They live in the OS keychain (for example through `keyring`), the MCP client's own secure store, or the vendor CLI's login. OAuth is preferred where the vendor offers it.
- **A secret never goes in a URL, query string or install deeplink.** Non-secret flags such as Klaviyo's `?read-only=true` are fine. If the plugin ever takes settings through `userConfig`, every secret field is marked `sensitive: true`.
- They are never written to `stages.toml`, a report, a log, an example file or the repo. They are never passed as script arguments, because arguments leak into shell history and process lists.
- Use a separate, least-privilege key for the agent, with an expiry where the vendor supports one.
- **Stripe:** from December 2026 its MCP stops accepting full-access keys and restricted keys without the Agent tag (OAuth still works). The Stripe reference will say so.
- A test scans the repo for key-shaped strings, and `.gitignore` covers `.env*`.

### 5.6 Customer data is data, never instructions

These are all untrusted input:

- event names, which anyone with a public write key can send;
- campaign names and email bodies;
- support tickets, NPS verbatims and cancellation reasons;
- Stripe metadata;
- vendor "skill" or docs tools that return instructions.

Skills say so in plain words. Free text is summarised into themes for `forming-lifecycle-hypotheses` and never acted on. During this research, one vendor docs page was reported to contain text telling AI assistants to post feedback to an external URL. It was not followed.

### 5.7 Tests that hold the line

Safety rules only hold if CI checks them. These checks come in the Phase 1 foundations PRs (section 8) and apply to every later PR:

- **Offline by construction.**
  - A static check: no network imports (`socket`, `urllib`, `http.client`, `ssl` and similar) and no third-party imports in any skill script.
  - At run time, the test harness runs every script with sockets disabled, through a wrapper that patches `socket` before `runpy` runs the script. A script that tries to connect fails its test.
- **Replay bundles that copy real API quirks.** Synthetic vendor exports must reproduce what the real APIs do:
  - fields left out when they are zero or default;
  - nulls, and numbers sent as strings;
  - epoch and ISO timestamps;
  - gzip, zip and JSONL files;
  - duplicates from at-least-once webhooks, and out-of-order rows.

  Each quirk cites the vendor doc it came from. Another team's fake passed tests while live code crashed, because the real API left out zero fields.
- **Leak gate.** CI must find zero hits for:
  - client or prospect names;
  - real IDs;
  - `/Users/<name>` and `/home/<name>` paths;
  - token-shaped strings.

  The name denylist is stored as hashes, so the names never appear in the repo *(D16)*. Typesy and eReflect are allowed as the labelled worked example.
- **Docs match reality.**
  - Every script, reference, asset and MCP tool name that a `SKILL.md` mentions must exist. Script paths are already checked. Tool names are checked against the vendor capability matrix.
  - Every skill stays under its size cap: `SKILL.md` under 500 lines, and every file under 256 KiB.
  - Every vendor entry in `vendors.toml` encodes its rate limits, and the bridges and export recipes respect them.
- **Permissions and licences.**
  - Every permission file denies its vendor's Tier 3 tools.
  - Every skill with `adapted-from` has a `NOTICE.md`.
- **Two operating systems.** CI runs on Ubuntu **and macOS**, on Python 3.11 and 3.13. The other team's Linux-only failures came from `/bin` resolving to `/usr/bin`, coarse file modification times, and tests that wrote to `/private/tmp`.
- **One facts file.** `facts.json` holds the install commands, skill, script and test counts, and network behaviour. A test fails if it drifts from the repo, so the website can copy it instead of hard-coding "136 tests" or "no network calls".

---

## 6. What we adapt from open source, and under what licence

**How licences were checked.** On 2026-10-20 the **actual LICENSE file** of every source in the table was read, not GitHub's label. Each is MIT, ISC or Apache-2.0 as listed. PostHog's monorepo is MIT except its `ee/` folder. Anthropic's knowledge-work plugins have no per-plugin LICENSE file, so they fall under the repo-root Apache-2.0.

"Adapt" means taking a structure or idea and **rewriting it in our own voice, bound to our scripts**, with credit. Text is copied only where the licence allows, with the notice kept. The full research notes, with a URL for every claim, are summarised here (see D15).

**Learn-only, never copied:**
- anything under Commons Clause (for example, Customer.io's CLI is Apache-2.0 + Commons Clause);
- anything under a non-commercial or "no AI products" licence;
- any repo with no licence;
- any file whose own header says it came from such a source.

**The provenance trap.** A repo's licence covers only what its authors could license. So we check **each file's own lineage note**, not just the repo licence. In marketingskills at commit `e85f3cb`:

| File or skill | Lineage note | Our treatment |
|---|---|---|
| `emails` (SKILL.md and its three references) | None | Adaptable under MIT |
| `copywriting`, `copy-editing` | Parts adapted from Profound's [skills-marketing-library](https://github.com/retieedra-profound/skills-marketing-library) (MIT, LICENSE read) | Adaptable. Credit both repos |
| `copywriting/references/natural-transitions.md` | Adapted from the University of Manchester Academic Phrasebank | **Learn-only** (not openly licensed) |
| `conversion-tracking` snippets | Adapted from [ConversionKit](https://github.com/ConversionKit/conversion-tracking) (MIT, LICENSE read) | Adaptable. Credit both repos |
| `pricing` teardown rubric | Written by the authors themselves, with the framing credited to Kyle Poyar's teardown | Adaptable if needed. Keep the credit to Poyar |
| `ads` references | Rewritten from a playbook under MIT + Commons Clause | **Learn-only**. We don't use them anyway |

Popularity isn't quality. skills.sh install counts can be inflated, so they never decide what we adapt.

| Source | Licence | Take | Leave | Lands in |
|---|---|---|---|---|
| [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) (55k★) | MIT, no NOTICE file | **`emails`:** sequence types (welcome, onboarding, re-engagement, win-back, billing) and the per-email output template (trigger, goal, exit condition, segment). **`churn-prevention`:** cancel-flow and dunning structure. **`customer-research`:** confidence labels for survey evidence. **`conversion-tracking`:** grading each event by how its firing was verified. The `evals.json` shape, which we already use | Its sample-size tables. They give no formula, and they don't match the standard one: for 10% → 12% they say 8,700 per variant, where `holdout.py size` gives 3,841 at α = 0.05 and 80% power. "Save rate" with no counterfactual. Unsourced benchmarks. Open rates with no Apple Mail Privacy Protection caveat. Its Node CLIs, which can send and delete with dry-run off by default | `writing-lifecycle-emails`, `analyzing-retention-cohorts`, `measuring-customer-happiness`, `planning-product-tracking` |
| [PostHog `modeling-activation-metrics`](https://github.com/PostHog/posthog/blob/master/products/data_modeling/skills/modeling-activation-metrics/SKILL.md) | MIT (monorepo outside `ee/`; also in [PostHog/skills](https://github.com/PostHog/skills), MIT) | The closest match to our method. It scores early actions on reach and predictive power, excludes cohorts too young for the window, warns about confounds, flags guessed choices, and asks before any write. Cite it as prior art; reuse its SQL recipe shape for the PostHog export | HogQL-only assumptions | `finding-leading-indicators` references, `connecting-product-analytics` |
| [GrowthBook skills](https://github.com/growthbook/skills) | MIT ([gbstats](https://github.com/growthbook/growthbook/tree/main/packages/stats) also MIT) | Read-only design and analysis kept apart from writes. Health checks before results; interpretation stops on SRM. One or two goal metrics plus at least one guardrail. A learnings log | gbstats as a dependency (it needs numpy and scipy). Use it only as an offline test oracle | A/B extension, `forming-lifecycle-hypotheses` |
| [Mixpanel ai-plugins](https://github.com/mixpanel/ai-plugins) | Apache-2.0, no NOTICE file | `manage-experiment`: a peek-safety table and a hard guardrail gate. `monitor-metrics`: seasonal baseline, robust residuals and 30-vs-30-day drift tests, which stdlib can reproduce for the indicator monitor | Its per-user-ID outlier branch, which breaks the "no IDs" rule | `building-monitoring-dashboards`, `planning-product-tracking` |
| [Amplitude mcp-marketplace](https://github.com/amplitude/mcp-marketplace) | MIT | `tracking-plan-audit` and `taxonomy` rules: confirm before any write, put proposals on a branch and never on main, never infer an ID from a name | [amplitude/builder-skills](https://github.com/amplitude/builder-skills): **no LICENSE file**, so nothing is taken. Its readout also asks for post-hoc segments and extends underpowered tests | `planning-product-tracking`, `connecting-product-analytics` |
| [accoil/product-tracking-skills](https://github.com/accoil/product-tracking-skills) | MIT | The audit is a factual inventory: current state, then a target plan, then a delta file | — | `planning-product-tracking` |
| [RudderStack agent skills](https://github.com/rudderlabs/rudder-agent-skills) | MIT | `rudder-tracking-plans`: the tracking plan as a schema contract that events are validated against. No official Segment skill was found | Its `rudder-cli` dependency | `planning-product-tracking` |
| [Statsig agent-skills](https://github.com/statsig-io/agent-skills) | ISC | The shape of a small stdlib client: a reference for what we *don't* need to build, because MCP servers do it | Its statistics content, which is thin | `connecting-product-analytics` |
| [anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) | Apache-2.0 | `small-business/reactivate`: "quiet" judged against each customer's own rhythm, a first message that doesn't pitch, owner approval per batch. `data/validate-data`, `data/statistical-analysis` checklists | `data/build-dashboard`, which claims to work offline but loads Chart.js from a CDN. Per-customer lists (we report counts) | Win-back stage, dashboards |
| [anthropics/skills](https://github.com/anthropics/skills) | **Mixed.** Most skills are Apache-2.0; `docx`, `pdf`, `pptx` and `xlsx` are **proprietary** | `skill-creator`: eval and benchmark schemas, and its stdlib static review page as a pattern for `dashboard.py` | Anything from `docx`, `pdf`, `pptx` or `xlsx`, including copies redistributed in other lists | Evals, `building-monitoring-dashboards` |
| [RefoundAI/lenny-skills](https://github.com/RefoundAI/lenny-skills) | MIT for the repo, but the README reserves the quoted podcast content to Lenny and his guests | **Ideas only, never text.** Themes for activation, retention, PMF and referral stages | All text. It also states thresholds (for example 40% "very disappointed") as rules | Background reading in references |
| Do **not** use | — | [deanpeters/Product-Manager-Skills](https://github.com/deanpeters/Product-Manager-Skills) (CC BY-NC-SA 4.0, non-commercial); RFM and Lenny-derived packs with no licence | | |

**Statistical cross-checks, used as test oracles only, never shipped:**

- gbstats (MIT);
- k-dense `statistical-power` (MIT, needs statsmodels);
- [send-experiment-designer](https://github.com/aaron-he-zhu/aaron-marketing-skills/blob/main/email/deliver/send-experiment-designer/SKILL.md) (Apache-2.0). It uses open rate as a primary metric, which we won't.

### How we credit

The Agent Skills [specification](https://agentskills.io/specification) has `license` and a free-form `metadata` map, but no attribution field. So, for every adapted skill:

1. **A `NOTICE.md` inside the skill folder**, because folders install alone. It holds the source, the copyright line, the full licence text, the upstream URL and commit, and the **credit chain**: the upstream's own upstreams, e.g. Profound or ConversionKit. For Apache-2.0 it also states what we changed.
2. **Frontmatter** keeps `license: MIT` and adds metadata keys, e.g. `adapted-from: "coreyhaines31/marketingskills@<sha>:skills/emails"` and `upstream-license: "MIT"`. If Apache-2.0 text is included, the field becomes `license: MIT AND Apache-2.0` with a pointer to `NOTICE.md`.
3. **A root `THIRD_PARTY_NOTICES.md`** listing every adapted source.
4. **`validate_skills.py` checks** that any skill with `adapted-from` has a `NOTICE.md`. Today it requires `license` to be exactly `MIT`, so it will also accept `MIT AND Apache-2.0` when a `NOTICE.md` is present.

Adapt from GitHub at a pinned commit, never from locally installed copies. The copies installed here on 2026-09-16 are already stale (`emails` 2.0.0 vs 2.1.4 upstream). Upstream has since fixed issues they still carry: p-value wording, the aha-moment definition, and an unvalidated health score.

---

## 7. Gaps in the lifecycle stack

The founder asked what's missing. The goals are conversion, retention and happy customers. These are the gaps that most often decide those numbers, and where each one would land.

| Gap | Why it matters | Where it lands |
|---|---|---|
| **Churn and win-back** | Retention is a stage with its own adoption point, and cancelled customers are a stage of their own. Involuntary churn (failed payments) is often a large share of the total and needs dunning, not persuasion | `analyzing-retention-cohorts` (voluntary vs involuntary split), and win-back as a stage in `stages.toml`. Cancel-flow and dunning playbooks adapted from marketingskills `churn-prevention` |
| **Onboarding UX and in-product channels** | Most adoption points are reached in the product, not the inbox. Email is one channel of several | A `channel` column and per-channel caps in `designing-state-journeys`. In-app patterns compose with marketingskills `onboarding`, credited, without copying |
| **Pricing and paywall tests** | Revenue metrics are heavy-tailed. A price that lifts conversion can cut renewal months later | Mean metrics and guardrails in the A/B extension, with first renewal as a pre-registered long-horizon guardrail. Composes with marketingskills `pricing` and `paywalls` |
| **NPS, CSAT and "customer happy" signals** | Happiness is the slowest-moving outcome and the easiest to fake with a biased sample | `measuring-customer-happiness`: response rates, a non-response bias check, intervals, and happiness as a guardrail on every test |
| **Deliverability** | An email in spam is not reach. Bulk-sender rules from Gmail and Yahoo (authentication, one-click unsubscribe, a complaint-rate ceiling) decide whether the treatment arm is treated at all | Bounce, complaint and unsubscribe checks in `audit_sends.py`, plus a deliverability checklist in `designing-state-journeys` |
| **Frequency fatigue** | Lifecycle, newsletters and product updates share one inbox. Over-contact shows up as unsubscribes, which shrink the reachable audience for every later stage | A `program` column and cross-program contact pressure in `audit_sends.py`. A **global long-term holdout** pattern measures cumulative value and fatigue |
| **Attribution limits** | ESP dashboards credit conversions to emails that didn't cause them. Teams then optimise the dashboard | A short doc, `docs/attribution-limits.md`, plus readout wording: only holdouts make causal claims. No per-email credit |
| **Data quality and tracking plans** | Every analysis here assumes the events exist, are named consistently and are attributed to the right actor | `planning-product-tracking`, run before any analysis |
| **Identity and unit of analysis** | B2B outcomes are per account while behaviour is per user, and households have the same split. Anonymous-to-known merges double-count | `unit` in `stages.toml`; identity coverage in `tracking_audit.py`; the `actor` and reader rules extended to accounts |
| **Consent and privacy** | Marketing consent differs from transactional. Exports outlive their purpose | A checklist in the connecting skills: consent source, retention of exports, pseudonymised views. Not legal advice |
| **Interference in referral and social tests** | One user's treatment reaches their friends, which breaks the comparison | Cluster randomisation (by household, team or referrer) in the A/B extension |
| **Novelty, seasonality, overlapping tests** | Week-one effects fade. Two tests on the same segment and stage contaminate each other | Full-week horizons; `forming-lifecycle-hypotheses` flags overlapping tests |
| **A learning log** | Teams re-test old ideas and forget nulls | Decision records indexed by `forming-lifecycle-hypotheses`; every hypothesis has a version and a "supersedes" link |
| **The "why" behind the numbers** | Scripts show where and how much. Interviews and verbatims show why | Compose with marketingskills `customer-research`. Verbatims feed hypotheses as *qualitative* evidence, never as proof |
| **Value sizing** | A team can't prioritise without knowing what one point is worth | `adoption_map.py` reports customers lost per stage. An optional revenue column turns that into money, using the team's own numbers |

---

## 8. Build order

Each PR is one coherent skill or extension. Each PR includes:

- the contract change;
- the planted truths;
- the tests;
- evals with at least 3 cases;
- the four checks, plus `claude plugin validate --strict .`.

No PR merges without the founder's approval. Each phase ends in a minor release.

### Phase 0: this PR
`docs/roadmap.md` only. Decisions in section 9.

### Phase 1a: foundations (repo hardening, no new skills)
| PR | Work |
|---|---|
| F1 | `facts.json` plus a drift test (install commands, counts, network behaviour) for the website to copy. **Opened alongside this roadmap** |
| F2 | CI on Ubuntu and macOS. The offline test harness (sockets disabled), the static import checks, the leak gate (D16) and the size caps |
| F3 | If D14 says yes: shrink the existing Practica files under 256 KiB, with every planted truth and test unchanged |
| F4 | `.codex-plugin/plugin.json`; validator support for `adapted-from` and `NOTICE.md`; a root `THIRD_PARTY_NOTICES.md` |

### Phase 1: the adoption map (offline, the organising idea) → 0.2.0
| PR | Work |
|---|---|
| 1 | `stages.toml` and wide `accounts.csv` contracts; Practica `lifecycle/` dataset; `mapping-adoption-stages` + `adoption_map.py` |
| 2 | `finding-leading-indicators`: `--stages/--stage`, time-to-adoption-point table |
| 3 | Refactor: move the scoring core of `score_signals.py` into `scripts/shared/signals.py` (no behaviour change; every existing test unchanged) |
| 4 | `splitting-customer-segments` + `segment_split.py` (embeds the shared scoring block) |
| 5 | `designing-lifecycle-states`: segment-aware rules; update `method.md` with the stage loop |

### Phase 2: connect and track (read-only) → 0.3.0
| PR | Work |
|---|---|
| 6 | `planning-product-tracking` + `tracking_audit.py` + `tracking/` dataset |
| 7 | `connecting-product-analytics` + `analytics_bridge.py` |
| 8 | `connecting-data-warehouses` + `extract_sql.py` (including billing outcome sources) |
| 9 | `connecting-email-platforms` + `esp_bridge.py` (sends, policy drift, live templates) |

### Phase 3: hypothesise, test, monitor → 0.4.0
| PR | Work |
|---|---|
| 10 | `forming-lifecycle-hypotheses` + `hypotheses.py` |
| 11 | A/B/n sizing and assignment in `holdout.py`; `prereg.toml` arms and guardrails |
| 12 | A/B/n, mean metrics and guardrails in `readout.py` |
| 13 | `building-monitoring-dashboards` + `dashboard.py` |

### Phase 4: retention, happiness, emails, channels → 0.5.0
| PR | Work |
|---|---|
| 14 | `analyzing-retention-cohorts` + `retention.py` |
| 15 | `measuring-customer-happiness` + `happiness.py` |
| 16 | `writing-lifecycle-emails` (adapted from marketingskills `emails`, with NOTICE) |
| 17 | `designing-state-journeys`: channel, program, deliverability and fatigue checks |

### Phase 5: write proposals, then 1.0
| PR | Work |
|---|---|
| 18 | Tier 2 change plans: `change_plan.py` (plan, hash, expiry, the 20-operation cap, read-back, receipt, revert) and its use in the connecting skills, only after read-only use has been proven |
| 19 | Method v2, README, CHANGELOG, plugin version; a hand-over note for the website session |

Rough size: about 2–3 agent-days per phase with review, longer for Phase 3. These are estimates, not commitments. Phases 2 and 3 can swap if the founder wants testing before integrations *(Decision D6)*.

---

## 9. Decisions needed

Each decision has a recommendation. The first five block Phase 1. The rest can wait until their phase starts.

### Before Phase 1

| # | Decision | Recommendation | Alternatives |
|---|---|---|---|
| D1 | **Public term** for the per-segment, per-stage indicator | **"Adoption point"** in copy and new skills; keep "leading indicator" as the technical term and in existing skill names; never "PAI" | "Product adoption indicator" (drop the acronym); "tipping point" |
| D2 | **v2 scope** | All eleven new skills, built in phase order. Each phase ships on its own, so the plan can stop after any phase | Phases 1–3 only for now; defer retention, happiness and emails |
| D3 | **Segments as their own skill** | Yes: `splitting-customer-segments` is separate from `mapping-adoption-stages`. It answers a different question ("do segments need different adoption points?") and matches the process: split, then find the tipping point | One combined skill, which means fewer skills but a broader trigger |
| D6 | **Build order** | Adoption map first (Phase 1), then connect and track, then test and monitor | Integrations first, because they remove tab-switching soonest, while the analysis waits a phase |
| D14 | **Example files over 256 KiB** (six today) | PR F3, before Phase 1: shrink the Practica files under the limit and keep every planted truth, proved by the same tests. Confirm the directory rule first | Leave them, and accept the directory hold |

### Before Phases 2–5

| # | Decision | Recommendation | Alternatives |
|---|---|---|---|
| D4 | **Email skill** (Phase 4) | A new `writing-lifecycle-emails` that absorbs `grounding-lifecycle-emails`: craft adapted from marketingskills `emails` (MIT, credited), plus our pipeline and claim checker. Keep the old name as a short pointer for one release | Extend `grounding-lifecycle-emails` in place. That's less churn, but the name doesn't trigger on "write an email" |
| D5 | **A/B tests** (Phase 3) | Extend `designing-holdout-experiments` and `readout.py`, so one pre-registration format, one readout and one set of gates cover both. Broaden the description | A separate `designing-ab-tests` skill sharing the scripts |
| D7 | **Tier 3 actions** (send, launch, activate, delete) | **Never by the agent**, even with approval. A person does them in the platform. This matches method principle 1 | Allowed for one named action with explicit approval in the moment |
| D8 | **Tier 2 writes** (draft templates, tracking-plan entries, inactive flags) | Not in 0.x. Add them in Phase 5, after read-only use has been proven | Allow from Phase 2 with approval |
| D9 | **Integration granularity** | Three skills by category, with one reference file per vendor | One skill per vendor, which triggers better but means 15+ skills to maintain |
| D10 | **Adapting third-party content** | Adapt only from permissive licences (section 6). Ship a `NOTICE` inside each adapted skill folder, because folders install alone. Add a root `THIRD_PARTY_NOTICES.md` and an `adapted-from` metadata key in frontmatter, and have `validate_skills.py` check all three | Write everything from scratch and only link to other repos |
| D11 | **Typesy figures** | Keep using only figures that are already published. Any renewal-stage Typesy numbers need eReflect's written approval first. Until then the example says "not yet measured" | Patterns only, no numbers |
| D12 | **Dashboard delivery** | A static `dashboard.html` the team can open or host privately. No hosted service | Add templates for GitHub Pages or a BI tool export |
| D13 | **An MCP server that wraps our scripts** (from the v1 plan's "later" list) | After 1.0 | Within v2, for MCP-only agents |
| D15 | **Research notes** | Commit condensed versions under `docs/research/`, so contributors can check vendor facts and each one carries the date it was checked | Keep them out of the repo, since vendor facts go stale fast |
| D16 | **Leak-gate name list** | Store client and prospect names as salted hashes in the repo. CI hashes each word it scans and compares, so the names never appear in plain text | Keep the list in a CI secret (harder for contributors to run locally) |

---

## 10. Not doing

- **Sending, scheduling or launching.** The agent prepares; a person presses send in their own platform.
- **Bandits, per-user optimisation, send-time optimisation.** At the volumes most teams have, they learn noise (lesson 13).
- **Multi-touch attribution or marketing-mix models.** The ESP's "attributed revenue" is reported under that name and never as lift.
- **A hosted service, database or daemon.** Scripts stay offline. Vendor access only goes through MCP servers the user installs.
- **Re-implementing vendor API clients** where an official MCP server exists.
- **Sequential testing or always-valid p-values** in v2. Fixed horizons stay, with no peeking. This could come later, pre-registered.
- **pandas, numpy, scipy or YAML.**
- **Typesy-specific fields in any skill.** Typesy appears only as a labelled worked example.
- **Content from repos whose licence doesn't allow reuse.**

---

## 11. Sources

Vendor and licence facts were checked on 2026-10-20. Links are inline in sections 4–6. Key sources:

- **Founder's planning docs:** `open-source-plan.md`, `open-source-journeys-and-emails.md` (private, outside the repo).
- **Repo:** [`method.md`](method.md), [`lessons.md`](lessons.md), [`data-contracts.md`](data-contracts.md), [`case-study-typesy.md`](case-study-typesy.md).
- **Protocol and client controls:** [MCP specification, tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools); [MCP security best practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices); [Claude Code permissions](https://code.claude.com/docs/en/permissions); [Agent Skills specification](https://agentskills.io/specification).
- **Deliverability:** [Gmail sender guidelines](https://support.google.com/a/answer/81126) (spam rate below 0.30%, aim for below 0.10%; one-click unsubscribe; SPF, DKIM and DMARC); [Yahoo sender best practices](https://senders.yahooinc.com/best-practices/) (complaints below 0.3%; honour unsubscribes within 2 days).
- **Lessons from another team** that open-sourced an ads MCP server and skills: the write-approval protocol, the testing rules and the provenance trap (shared through the project overview, 2026-10-20).
- **Postgres MCP vulnerability:** [Datadog Security Labs](https://securitylabs.datadoghq.com/articles/mcp-vulnerability-case-study-SQL-injection-in-the-postgresql-mcp-server/).
- **Open-source skills:** every repo linked in section 6. Licences were confirmed with the GitHub API: marketingskills MIT; lenny-skills MIT (content reserved in the README); GrowthBook skills MIT; Statsig ISC; Mixpanel Apache-2.0; knowledge-work-plugins Apache-2.0; Amplitude mcp-marketplace MIT; Amplitude builder-skills none; PostHog/skills MIT; accoil MIT; RudderStack MIT.
- **Full research notes**, with a URL beside every claim and the open UNVERIFIED items, are held outside the repo for now (open-source skills, email platforms, and analytics, warehouses, billing and feedback). They can be committed under `docs/research/` *(D15)*.
