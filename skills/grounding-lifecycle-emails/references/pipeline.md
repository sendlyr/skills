# The pipeline in detail

## 1. Safe and blocked facts (code, not the model)

Write one function per program that turns a user's data into three things:

```python
def safe_facts(user):
    safe, blocked = [], [
        "No exact minutes, seconds or trial-day numbers.",
        "Never mention features without a data source (e.g. typing tests).",
    ]
    if user.lessons_completed > 0:
        safe.append("Has completed at least one lesson.")
    else:
        blocked.append("Do not claim a completed lesson.")
    if user.goal_set:
        safe.append("Has set a learning goal.")
    else:
        blocked.append("Do not refer to their goal; they haven't set one.")
    if user.current_lesson_name:
        safe.append(f"Current lesson: {user.current_lesson_name}.")
    level = "metric" if user.lessons_completed > 0 else ("behaviour" if safe else "light")
    return {"safeFacts": safe, "blockedFacts": blocked, "personalisationLevel": level,
            "verifiedFirstName": user.first_name_from_verified_source or ""}
```

The model sees both lists. The claim checker enforces the blocked ones as `fact_rules`.

## 2. Objective step

- **Input:** state, state chain (where the user has been), previous emails to this user, safe and blocked facts, product memory (overview, value props, voice, approved and prohibited claims, CTA library, this state's playbook).
- **Output:** `{emailObjective, emailAngle, suggestedCtaKey, personalisationNotes, riskWarning}`.
- **Validation:** required keys present; the CTA key is in the library.
- **Fallback:** a deterministic objective per state, including history-aware angles (recovered vs direct path).

Splitting objective from copy keeps strategy auditable. A reviewer can disagree with the objective without reading prose.

## 3. Copy step

- **Input:** the objective, voice, safety rules, safe and blocked facts, the selected CTA from the allowlist, the verified name or empty.
- **Output:** `{subject, preheader, headline, intro, body[], cta_label, cta_url, footer}`.
- **Post-processing:**
  - overwrite the CTA from the allowlist;
  - force the fallback greeting when there is no verified name;
  - strip any HTML;
  - retry once on invalid JSON.

## 4. Claim check

`claim_check.py` with `claim-rules.toml`. Blockers stop the email; warnings go to the reviewer. Rule families:

| Family | Catches |
|---|---|
| `prohibited` | Unsupported or pressure phrases |
| `pattern` | Regex rules, e.g. exact metrics |
| `fact_rule` | Claims the facts contradict |
| `cta` | A label or URL not in the allowlist |
| `greeting` | Unverified or wrong names |
| `product_name` | Internal names |
| `required` | Missing footer or unsubscribe link |
| template families | Unknown placeholders, literal names or values in the template, cross-user name leaks |

## 5. Render

A fixed template (ESP or code) turns the JSON into HTML and text. The model never produces HTML. If you allow an "AI edits HTML" feature, treat it as a separate, explicitly reviewed path.

## 6. Review and approval

- Every draft is **pending** until a human approves, edits or rejects it.
- Group approval only applies to drafts without blockers.
- Approving a template is per state and per template version. Sending still re-checks at send time.

## 7. Traces

For every draft, store a run ID and, per step: prompt version, memory version, model, input summary, output, duration and error. When a strange email appears, the trace shows which input made it.
