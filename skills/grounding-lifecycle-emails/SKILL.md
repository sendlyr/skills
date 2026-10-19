---
name: grounding-lifecycle-emails
description: Write AI-assisted lifecycle and onboarding emails that are grounded in approved product facts and in each user's real behaviour. Covers a reviewed product memory, deterministic safe and blocked facts, a split pipeline (an objective step that writes no copy, then a copy step that returns structured JSON and no HTML), a rule-based claim checker run before human review, group-template safety, and mandatory human approval. Use when generating onboarding, activation, trial or re-engagement emails with an LLM, building per-state templates, or checking drafts for false claims, wrong names, unapproved CTAs or pressure language. Complements copywriting skills; this one owns truth and safety, not tone.
license: MIT
metadata:
  author: sendlyr
  version: "0.1.0"
---

# Grounding lifecycle emails

An AI can write a good lifecycle email. It can also tell a user they finished a lesson they never started, greet them by their email username, promise "fluent in 7 days", or link to checkout in a trial that converts automatically. This skill puts the AI inside a pipeline where code decides what's true, the AI only writes, a checker catches known mistakes, and a human approves every email.

> *"The AI does not decide who to contact, does not send email, and does not generate raw HTML."*

## When to use

- Generating per-state onboarding or trial emails (after `designing-lifecycle-states` and `designing-state-journeys`).
- Turning one good email into a safe template for a whole state group.
- Reviewing AI drafts before a human sees them.

For tone, structure and persuasion, pair this with a copywriting skill (e.g. marketingskills `copywriting` / `emails`). This skill doesn't replace them.

## The pipeline

```
user state + facts
  → approved product memory          (human-reviewed; only approved entries reach a prompt)
  → safe / blocked facts             (code decides what may be said about this user)
  → objective step                   (LLM → JSON: objective, angle, CTA key, notes, risk; writes no copy)
  → copy step                        (LLM → JSON: subject, preheader, headline, intro, body[], cta, footer; no HTML)
  → claim check                      (scripts/claim_check.py: blockers and warnings)
  → fixed template render            (your ESP or renderer; the AI never writes HTML)
  → human review → approve / edit / reject
```

## Method

1. **Seed product memory** from `assets/product-memory.md`. Each entry records its source, version and approval:
   - Product Overview, Value Propositions, Brand Voice;
   - Approved Claims, High-Risk Claims, Prohibited Claims;
   - CTA Library, State Playbook (objective, angle and *avoid* per state);
   - Benchmark Notes, Brand Assets, Source Notes.

   Website scans start as **unapproved**. A human approves each claim. See `references/product-memory.md`.
2. **Define safe and blocked facts** per state (`references/pipeline.md`). Code computes these from the user's data:
   - **safe**: "has set a goal", "current lesson is X";
   - **blocked**: "don't claim completion when lessons = 0", "no exact minutes", "no data you don't have";
   - a **personalisation level** (`metric` / `behaviour` / `light`).
3. **Write `claim-rules.toml`** from `assets/claim-rules.toml`: product naming, the CTA allowlist (label and URL pairs), prohibited phrases (blocker or warning), regex patterns, fact rules, greeting rules, required parts, and allowed template placeholders.
4. **Run the objective step**, prompt in `assets/objective-prompt.md`. Input: state, state playbook, product memory, safe and blocked facts, previous emails to this user. Output: JSON only. It writes no copy.
5. **Run the copy step**, prompt in `assets/copy-prompt.md`. Output: JSON fields only, no HTML. The CTA is overwritten from the allowlist; never trust the model's URL. Use a name only if it comes from a verified field.
6. **Check every draft:**

   ```bash
   python3 scripts/claim_check.py --rules claim-rules.toml --emails emails.json --out claim-report/
   ```

   Exit code 1 means a blocker. Fix it, or regenerate. Warnings go to the reviewer.
7. **For group templates** (one template per state, rendered per user), put the template and the renders in `emails.json` (template mode). The checker also blocks unknown placeholders, a literal customer name or count in the template, and one user's name appearing in another user's email.
8. **A human approves.** Groups with blockers can't be bulk-approved. Record prompt version, memory version, model, inputs and outputs for every draft, so a reviewer can see why an email says what it says.
9. **Render at send time** (`designing-state-journeys`). Facts change; approved templates don't.

## Copy rules that held up (from Typesy)

- Write to **the person who reads the email**, about something they can do now. Typesy Homeschool writes to the parent, not the child.
- **One goal, one CTA.** Prose for engagement emails; numbered steps only for first-time setup.
- **Don't re-explain the product** after the first email. Refer to "the next pet", not all 50 pets.
- **Be concrete about effort:** "15 minutes" or "one lesson", not "a little time".
- **No internal vocabulary** in customer copy: the tool's name, "experiment", "state", internal metric names, internal plan names.
- **No pressure in an auto-converting trial:** no "upgrade", "checkout" or "last chance".
- "Click", not "tap", in email.
- Use only template syntax your renderer supports. Unsupported filters crashed Typesy renders.

More in `references/copy-rules.md`.

## Run on the example

From the repo root:

```bash
python3 skills/grounding-lifecycle-emails/scripts/claim_check.py \
  --rules examples/practica/emails/claim-rules.toml \
  --emails examples/practica/emails/emails.json --out /tmp/claims
```

Nine drafts. Two are clean, one has warnings only, and six are blocked:
- a false completion claim;
- an unapproved CTA;
- "fluent in 7 days, guaranteed";
- an exact usage metric;
- a greeting guessed from a username;
- an internal plan name with no unsubscribe link.

`template.json` shows the group-template checks.

## Gotchas

- **The checker catches known mistakes only.** A human still approves every email.
- **Blocked facts must be explicit.** If the data source doesn't cover a feature (Typesy VIP had no typing-test data), say "never mention it". Otherwise the model will, helpfully.
- **Names are operational data, not memory.** Never infer a name from an email address; fall back to "Hi there,".
- **Same state, different facts.** Render per user at send time; never reuse a rendered draft.
- **Website copy isn't approval.** Scraped claims ("447 hours saved", "23X faster") stay prohibited until a human approves them.

## References

- `references/product-memory.md`: schema, memory types, provenance, approval.
- `references/pipeline.md`: safe and blocked facts, each step's inputs and outputs, fallbacks, traces.
- `references/copy-rules.md`: craft rules with before and after examples.
- `references/esp-templates.md`: exporting structured JSON to Liquid (Braze, Customer.io) and Handlebars (Iterable).
- `assets/`: `product-memory.md`, `claim-rules.toml`, `objective-prompt.md`, `copy-prompt.md`.
