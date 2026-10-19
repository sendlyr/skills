# Audit queries (warehouse version)

`audit_sends.py` answers these from CSVs. If your data is in a warehouse, these Postgres-flavoured queries answer the same questions. They assume four tables:

- `assignments(user_id, arm, assigned_at, eligible)`
- `sends(user_id, sent_at, status, state_at_send, rendered_at)`
- `state_snapshots(user_id, observed_at, state, …facts)`
- `outcomes(user_id, converted)`

Run them read-only. Review row-level outputs internally; publish only aggregates.

## 1. Where did the sends go?

```sql
select state_at_send, count(*) as sends,
       round(100.0 * count(*) / sum(count(*)) over (), 1) as pct
from sends s join assignments a using (user_id)
where a.arm = 'treatment' and s.status in ('sent', 'delivered')
group by 1 order by 2 desc;
```

If the success state (or states past the indicator) holds most of the sends, the targeting is the problem.

## 2. Reach against the eligible denominator, within the SLA

```sql
with first_contact as (
  select user_id, min(sent_at) as first_at
  from sends where status in ('sent', 'delivered', 'not_needed') group by 1
)
select count(*) filter (where f.first_at <= a.assigned_at + interval '48 hours')::float / count(*) as timely_reach,
       count(*) as eligible_treatment
from assignments a left join first_contact f using (user_id)
where a.arm = 'treatment' and a.eligible
  and a.assigned_at + interval '48 hours' <= now();
```

## 3. Sequence patterns

```sql
select n, path, count(*) as users from (
  select user_id, count(*) as n,
         string_agg(state_at_send, ' -> ' order by sent_at) as path
  from sends where status in ('sent', 'delivered') group by 1) t
group by 1, 2 order by 3 desc limit 30;
```

## 4. Cap and spacing violations

```sql
with s as (
  select user_id, sent_at,
         lag(sent_at) over (partition by user_id order by sent_at) as prev
  from sends where status in ('sent', 'delivered'))
select count(distinct user_id) filter (where cnt > 3) as users_over_cap,
       (select count(*) from s where prev is not null and sent_at - prev < interval '24 hours') as sub_24h_gaps
from (select user_id, count(*) as cnt from s group by 1) c;
```

## 5. Staleness: render to send

```sql
select percentile_cont(0.5) within group (order by extract(epoch from sent_at - rendered_at) / 3600) as p50_hours,
       max(extract(epoch from sent_at - rendered_at) / 3600) as max_hours
from sends where status in ('sent', 'delivered') and rendered_at is not null;
```

## 6. Did each state's message make that state's ask?

Export the sent subject, CTA and text by state. A human reads them. A text heuristic (does a no-child message mention adding a child?) can triage, but a person decides.

## 7. Control contamination

```sql
select count(distinct s.user_id)
from sends s join assignments a using (user_id)
where a.arm = 'control' and s.status in ('sent', 'delivered');
```

## Two traps when writing your own

- **Snapshot flags:** `is_active = true` may mean "in the latest import", not "ever seen". Use the full snapshot history for "was this user visible?"
- **Default-false outcomes:** check that `converted = false` really means measured-and-not-converted. Otherwise use a measured flag.
