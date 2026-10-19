# skills.sh badge

## The line

```markdown
[![skills.sh](https://skills.sh/b/sendlyr/skills)](https://skills.sh/sendlyr/skills)
```

This matches the format in the [skills.sh docs](https://skills.sh/docs): `https://skills.sh/b/owner/repo` for the image, and `https://skills.sh/owner/repo` for the link. The docs' own example is `anthropics/skills`.

## Don't add it yet

On 2026-10-20 skills.sh didn't know this repo yet:

- `https://skills.sh/b/sendlyr/skills` returns a red badge that says **"custom badge: resource not found"**.
- `https://skills.sh/sendlyr/skills` returns 404.

skills.sh lists a repo through the anonymous telemetry of the `skills` CLI. In the FAQ's words, skills "appear on the leaderboard automatically through anonymous telemetry when users run npx skills add <owner/repo>". There is no form to fill in and no minimum is stated. So the first install creates the page and the badge. The install smoke test in the [launch-day checklist](checklist.md) does that.

To check whether the badge is ready:

```bash
curl -sL https://www.skills.sh/b/sendlyr/skills | grep -o 'aria-label="[^"]*"'
```

`aria-label="custom badge: resource not found"` means not yet. A label such as `Skills: 12` means it's ready.

## Where it goes in README.md

Put it directly under the title, in a one-line PR, once the badge is ready:

```diff
 # Sendlyr skills

+[![skills.sh](https://skills.sh/b/sendlyr/skills)](https://skills.sh/sendlyr/skills)
+
 **The measurement layer under lifecycle.** Six agent skills, with small dependency-free scripts:
```

The README is unchanged in this PR on purpose. Adding the line now would show a red "resource not found" badge on launch day.
