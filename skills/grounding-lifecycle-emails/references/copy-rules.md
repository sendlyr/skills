# Copy rules (from Typesy, generalised)

## Write to the reader, about their next action

> ❌ "Your child hasn't hatched a pet yet. Keep practising!" (sent to the parent; practising is the child's action)
> ✅ "Sit with Mia for her first 15-minute lesson. The first pet hatches at the end of it."

## One goal, one CTA

> ❌ "Set your goal, try a lesson, and explore our games!"
> ✅ "Pick your goal. It takes one click, and your first lesson is built around it."

## Prose for engagement, steps for setup

Numbered steps fit the first setup email ("1. Open Admin, 2. Add a child, 3. Assign a curriculum"). Later emails read like coaching, not a manual.

## Don't re-explain

After the first email, refer to "the next pet" or "your next lesson". Don't explain the whole reward system again.

## Concrete effort

> ❌ "Just a little time each day."
> ✅ "One 5-minute lesson."

(Stating the effort a task takes is fine. Quoting a user's own usage back to them, like "you spent 23 minutes", is blocked by default; it reads as surveillance and is often stale.)

## No internal vocabulary

Never in customer copy: your tool's name, "experiment", "state", "segment", indicator codes, internal plan names. Typesy's internal "Typesy VIP" name was blocked; customers see "Typesy".

## No pressure in auto-converting trials

No "upgrade", "buy", "checkout", "last chance" or "lose your progress". The trial converts on its own; pressure only raises cancellations and complaints.

## Personalise only from verified facts

- A name comes only from a verified field; otherwise "Hi there,".
- Counts come from placeholders, never hard-coded.
- Multi-child or multi-seat accounts: don't pick one arbitrary name. Use "your child" or a list.

## Renderer reality

Use only the template syntax your renderer supports. Typesy's AI-written templates used Jinja filters that didn't exist, and the renders crashed. Give the model the exact allowed syntax, e.g. inline conditionals only: `{{ 's' if count != 1 else '' }}`.
