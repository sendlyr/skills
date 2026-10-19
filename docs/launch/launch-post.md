# Launch post: "Why our lifecycle experiment showed nothing"

Every figure below comes from [`docs/lessons.md`](../lessons.md) or [`docs/case-study-typesy.md`](../case-study-typesy.md). The source for each one is listed at the end. If you change a number, check it against those two files first.

---

## LinkedIn (about 2,200 characters; the limit is 3,000)

> **Why our lifecycle experiment showed nothing**
>
> In 2026 we ran two onboarding email experiments with eReflect's Typesy. Both had a control group. Both showed nothing.
>
> Typesy VIP: 76.8% of the treatment group converted. Control: 76.7%.
> Typesy Homeschool: 58.62% vs 58.38% on the behaviour we wanted to move.
>
> So we reviewed everything. The review ended with one sentence:
>
> "Neither experiment failed to show an effect. Neither was ever in a condition to measure one."
>
> Here is what went wrong.
>
> 1. Many people in the treatment group never got an email.
> VIP reached 70.3% of them. Homeschool reached 80.30% of eligible households. If part of a group is never treated, the effect is diluted. More users do not fix that.
>
> 2. The emails went to people who did not need them.
> In Homeschool, 73% of sends went to families who had already added a child. Those families convert at 57–59% anyway.
> The 149 families who had logged in but not added a child converted at 4.0%. They got 116 emails. A 3-email cap would have allowed about 450.
>
> 3. We tracked the wrong person's action.
> The parent reads the email. The child does the lessons. Our signal was a child's action.
> The big jump came from a parent action: adding a child. Conversion went from 4.0% to 46.8%.
>
> 4. Moving the behaviour did not move the outcome.
> In VIP, the emails raised the key behaviour from 57.7% to 69.4%. Conversion did not move. About 77% of control trials converted anyway, so there was little room to grow.
>
> So we changed the method:
> → No verdict if fewer than 90% of eligible users are reached.
> → People who already did the key action get no email.
> → The signal must be something the reader can do, inside the trial.
> → We compare the groups as assigned. Never "contacted vs not contacted".
>
> We turned each lesson into an open-source agent skill. There are six. They are MIT-licensed, with small Python scripts and no dependencies. They work in Claude Code, Codex, Cursor and other agents.
>
> A test is only useful if it can say "no", or "we did not measure that properly". Now ours can.
>
> The skills and the full lessons: github.com/sendlyr/skills
>
> Thank you to eReflect for letting us publish real numbers, including these ones.

**Posting notes**

- LinkedIn cuts the post after about two lines, behind "…see more". The first two lines are the hook. Keep them.
- LinkedIn often shows posts with links to fewer people. One option: replace the link line with "Link in the first comment", and post `https://github.com/sendlyr/skills` as the first comment.
- Tag eReflect's company page only if they agree.
- This essay is the centrepiece of the launch. After LinkedIn and X, share it in creator communities you already take part in. Post once in each, with the story first and the link second. Show HN is optional; don't build the launch around it.
- The post has no install commands on purpose. Install commands appear only where they have been tested (checklist steps 2 and 9).

---

## X / Twitter

### Single post (265 of 280 characters; X counts a link as 23)

> Our lifecycle email test showed nothing.
> Treatment: 76.8% converted. Control: 76.7%.
>
> Why? Only 70.3% of the treatment group got an email. That test could never measure an effect.
>
> We turned the lessons into 6 open-source agent skills (MIT):
> github.com/sendlyr/skills

### Optional thread (5 posts, each under 280)

> **1/** Our lifecycle email experiment showed nothing.
>
> Treatment: 76.8% converted. Control: 76.7%.
>
> So we asked why. The answer: "Neither experiment failed to show an effect. Neither was ever in a condition to measure one."

> **2/** Only 70.3% of the treatment group got an email. Our method now requires 90%.
>
> If part of a group is never treated, the effect is diluted. More users do not fix that.

> **3/** In our second test, 73% of emails went to families who had already done the key step. They convert at 57–59% anyway.
>
> The 149 families who were stuck converted at 4.0%. They got 116 emails.

> **4/** We tracked a child's action. But the parent reads the email.
>
> The big jump came from a parent action: adding a child. 4.0% → 46.8%.

> **5/** We turned each lesson into an open-source agent skill. Six skills, MIT, small Python scripts, no dependencies.
>
> Real numbers, mistakes included:
> github.com/sendlyr/skills

---

## Where each figure comes from

| Figure | Source |
|---|---|
| VIP conversion 76.8% (136/177) vs 76.7% (66/86) | case study, VIP table |
| Homeschool 58.62% vs 58.38% on the indicator | case study, Homeschool "Headline" |
| VIP reach 70.3% (189/269) | case study, VIP "Reading"; lessons §1 gives 70.26% |
| Homeschool reach 80.30% of eligible (534/665) | lessons §1, case study |
| 90% reach gate | lessons §1, case study |
| 73% of 848 sends (623) to households with a child already added | lessons §2 |
| Those households convert at 57–59% | lessons §2 |
| 149 households, 4.0%, 116 sends, about 450 under a 3-email cap | lessons §2 |
| Adding a child: 4.0% → 46.8% | lessons §2 and §4 |
| VIP indicator 57.7% → 69.4% | lessons §8, case study |
| About 77% of control trials converted | case study, VIP "Reading" |
| The quoted sentence | lessons intro |

"Six skills" is the number of skills in this repo. It is not a Typesy figure.
