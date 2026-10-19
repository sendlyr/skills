# Worked example: Typesy Homeschool

Typesy is eReflect's typing-education product. Typesy Homeschool is the family plan: a **parent** signs up, adds one or more **child** accounts, and the children do the lessons. Lifecycle emails go to the parent. The trial lasts 7 days and converts to paid automatically.

These are real production figures from 2026, published with permission.

## The indicator we started with

"3 or more pets hatched within 14 days" (children hatch a pet by finishing a course). It had been validated against **12-week retention**.

For a **7-day trial** it had two problems:

1. More than half the window fell after the payment decision.
2. Pets are a child behavior, and the email reader is the parent.

## Re-scoring inside the decision window

Cohort: 1,295 assignments with an in-window observation (out of 1,380). Ranked by lift × coverage:

| Candidate (within 7 days) | Coverage | Converts if hit | If miss | Lift | Lift × coverage |
|---|---:|---:|---:|---:|---:|
| parent_engagement_score ≥ 10 | 81.3% | 56.0% | 30.6% | 25.5pp | 20.7 |
| pets ≥ 2 | 77.5% | 56.2% | 34.2% | 22.0pp | 17.1 |
| child engagement ≥ 10 | 69.3% | 57.5% | 37.2% | 20.3pp | 14.1 |
| parent_engagement_score ≥ 25 | 62.7% | 58.1% | 39.8% | 18.4pp | 11.5 |
| *pets ≥ 3 (the original indicator)* | *57.8%* | *58.2%* | *41.9%* | *16.3pp* | *9.4* |
| pets ≥ 5 | 46.8% | 58.7% | 44.7% | 14.0pp | 8.1 |
| 2+ children | 60.4% | 53.2% | 48.3% | 4.9pp | 3.0 |

**The original indicator ranked fifth of seven.**

The top row is a trap. `parent_engagement_score` is the sum of the children's engagement scores **plus 25 when pets ≥ 3**, so it restates the old indicator inside itself. It also contains no parent action at all.

## The real cliff: a parent action

Every candidate above is a child behavior. Splitting out the parent's own step changed the picture:

| Funnel stage (within 7 days) | Users | Conversion |
|---|---:|---:|
| Parent logged in, **no child added** | 149 | **4.0%** |
| Child added, never active | 154 | 46.8% |
| Child active, < 2 pets | 105 | 57.1% |
| Child active, 2+ pets | 887 | 59.3% |

- **The whole cliff is adding a child: 4.0% vs 46.8%, a 42.8pp gap.** Everything after it is marginal.
- **Primary indicator chosen:** parent adds a child within 7 days. It has 88.5% coverage, 57.4% conversion when hit vs 4.0% when missed, a 53.4pp lift, and **lift × coverage ≈ 47.3**, against 17.1 for pets ≥ 2 and 9.4 for the original.
- **Supporting signal:** pets ≥ 2, for households that clear the first gate.

A pairwise test (Fisher exact, Holm-adjusted) on the funnel confirmed it:

| Pair | Difference | Holm p |
|---|---:|---:|
| No child vs child added, never active | 42.7pp | 2.0e-18 |
| Child added, never active vs active, < 2 pets | 10.4pp | 0.257 |
| Active, < 2 pets vs active, 2+ pets | 2.2pp | 0.676 |

## What generalises

1. Score inside the **decision window**, not a convenient longer one.
2. Split **actors**. Ask "who does this, and who reads our email?"
3. Look for the **earliest gate**: setup steps beat engagement counts.
4. **Nothing vs something:** as the pet threshold rose, conversion-if-hit barely moved (56.2% → 58.7%) while conversion-if-miss climbed (34.2% → 44.7%).
5. **Distrust composite scores** until you have read their formula.
6. **Still correlation.** The 149 households converting at 4% are the intervention population. Whether an email that gets them to add a child *raises* conversion is a question for a holdout.
