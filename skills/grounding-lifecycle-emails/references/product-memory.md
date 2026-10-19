# Product memory

Product memory grounds the pipeline in facts the business has approved. Markdown is the reviewed artifact. Your runtime store (a table, a JSON file) is what the pipeline reads.

## Memory types

`product_overview`, `value_prop`, `brand_voice`, `approved_claim`, `high_risk_claim`, `prohibited_claim`, `cta`, `state_playbook`, `benchmark_note`, `asset_note`, `email_example`, and, from website scans, `website_headline`, `website_value_prop`, `website_cta`, `website_brand_style`.

## Fields on every entry

| Field | Why |
|---|---|
| `memory_type`, `title`, `content` | What it is |
| `source_type`, `source_url` / `source_path`, `source_hash`, `source_updated_at` | Where it came from, and whether the source has changed since |
| `version` | So a draft can cite the memory version it used |
| `status` (`active` / `retired`) | Old claims retire; they aren't deleted |
| `approved_for_agent` (true / false) | **Only approved, active entries reach a prompt** |
| `approved_by`, `approved_at` | Who said it's true |

Seeding must be idempotent: re-running it never duplicates rows.

## Rules

- **Website scans default to unapproved.** A marketing page's "447 hours saved" or "23X faster" is a claim, not a fact. Keep it as high-risk or prohibited until someone approves it for a specific use.
- **Style and asset entries** (colours, logo) can be approved for the renderer when they make no claims.
- **Website CTAs are reference only.** The pipeline picks the CTA from the state playbook and the allowlist.
- **Customer names are operational data, not memory.** They come from a verified customer field at render time.
- **A state playbook per state:** objective (the one ask), angle, and *avoid*. Example for "set up but no first action":
  - Objective: get the first action done.
  - Angle: the setup is done; the next step is small.
  - Avoid: implying progress that doesn't exist.

## Example (Typesy VIP, abridged)

- Approved: "Includes a 7-day free trial." · "Supports up to 5 users on one plan." · "Works across devices and syncs progress."
- High-risk (not used): "Save 447 hours per month." · "Become up to 63% more efficient." · "23X faster results."
- Prohibited:
  - "Do not mention typing tests" (no reliable data source for this product);
  - "Do not claim a completed course when completedCourses = 0";
  - "Do not mention exact time spent in seconds";
  - "Do not imply the user will lose progress if they don't upgrade."
- Brand voice: "A friendly learning coach, not a salesperson."
