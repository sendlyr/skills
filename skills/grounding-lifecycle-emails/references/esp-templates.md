# Exporting to an email platform

The pipeline produces structured JSON per state. Your email platform renders it at send time.

## Mapping

| JSON field | Typical template slot |
|---|---|
| `subject`, `preheader` | Message subject and preview text |
| `headline` | Hero or H1 block |
| `intro`, `body[]` | Text blocks |
| `cta_label`, `cta_url` | Button |
| `footer` | Footer block (include the platform's unsubscribe tag) |

## Placeholders

Write templates with neutral placeholders (`{{ first_name }}`), then convert them for your platform:

- **Liquid** (Braze, Customer.io): `{{ first_name }}` usually maps to a user attribute, e.g. `{{ customer.first_name }}` or `{{ ${first_name} }}`, depending on the platform. Provide a default: `{{ customer.first_name | default: "there" }}`.
- **Handlebars** (Iterable): `{{firstName}}`, with defaults through the platform's helpers.

Check the exact attribute syntax in your platform's docs. Run `claim_check.py` on the neutral version *and* on a few real renders from the platform's preview.

## Keep the facts fresh

Pull facts (lesson counts, current lesson) from user attributes at send time. Don't paste values into the template. A template approved on Monday must still be true when it renders on Thursday.
