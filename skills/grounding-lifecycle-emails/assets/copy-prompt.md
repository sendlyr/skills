# Copy step: prompt template

**System**

> You are the Copy step of a lifecycle email pipeline for {{ product }}. Return valid JSON only, with keys: `subject`, `preheader`, `headline`, `intro`, `body` (an array of short paragraphs), `cta_label`, `cta_url`, `footer`. Do not generate HTML.

**User** (send as JSON)

```json
{
  "objective": {"emailObjective": "…", "emailAngle": "…", "suggestedCtaKey": "…", "personalisationNotes": "…"},
  "brandVoice": "…",
  "safetyRules": [
    "Customer-facing product name is {{ product }}. Never use internal names: {{ forbidden_names }}.",
    "Use only the provided facts. Never invent names, numbers, progress or features.",
    "Use first_name only if verifiedFirstName is present. Never infer a name from an email address. Otherwise open with: Hi there,",
    "Use safe facts; never use blocked facts.",
    "No exact minutes, seconds or trial-day numbers.",
    "No high-risk claims. None are approved in this request.",
    "No purchase, upgrade, pricing or checkout language. The trial converts automatically.",
    "One goal, one call to action. Prose; numbered steps only for first-time setup.",
    "Don't re-explain the whole product; this reader has seen the earlier emails.",
    "Say 'click', not 'tap'.",
    "Include the unsubscribe placeholder {{ unsubscribe_url }} in the footer."
  ],
  "verifiedFirstName": "{{ or empty }}",
  "safeFacts": ["…"],
  "blockedFacts": ["…"],
  "selectedCta": {"label": "{{ from the allowlist }}", "url": "{{ from the allowlist }}"},
  "approvedClaims": ["…"],
  "prohibitedClaims": ["…"]
}
```

**After the model returns:**

1. Parse the JSON strictly. Retry once on invalid output.
2. **Overwrite `cta_label` and `cta_url` with `selectedCta`.** Never trust model URLs.
3. If `verifiedFirstName` is empty, force the intro to start with "Hi there,".
4. Run `claim_check.py`. A blocker means regenerate or edit; it never goes to send.
5. Render with your fixed template (ESP or code). Save as **pending review**.

**For group templates:** ask for placeholders instead of values (`{{ first_name }}`, `{{ lessons_completed }}`), allowing only `[template].allowed_placeholders`. Render per user, then check the template and every render together.
