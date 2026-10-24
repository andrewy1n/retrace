---
title: Results
sidebar: never
full_width: true
---

```sql roles
select distinct evidence_role from tiger.result_rows order by evidence_role desc
```

<Dropdown name=role data={roles} value=evidence_role title="Evidence" defaultValue="final" />

```sql arms
with t as (
  select job_id, arm, count(distinct task_id)::int as tasks, count(*)::double as n, sum(passed)::double as k,
         sum(case when timed_out then 1 else 0 end)::int as timed_out,
         sum(case when timed_out then 0 else cost_credits end) as credits,
         sum(case when timed_out then 0 else 1 end)::double as m
  from tiger.result_rows
  where evidence_role = '${inputs.role.value}'
  group by 1, 2
), s as (select *, k / n as p, 3.8416 / n as z2n from t)
select job_id, arm, tasks, n::int as trials, k::int as passed, p as pass_rate,
  greatest(0, (p + z2n / 2) / (1 + z2n) - 1.96 * sqrt(p * (1 - p) / n + 3.8416 / (4 * n * n)) / (1 + z2n)) as ci_low,
  least(1, (p + z2n / 2) / (1 + z2n) + 1.96 * sqrt(p * (1 - p) / n + 3.8416 / (4 * n * n)) / (1 + z2n)) as ci_high,
  timed_out, credits, credits / nullif(m, 0) as credits_per_trial
from s
order by job_id, arm
```

<DataTable data={arms} rows=20 wrapTitles=true>
  <Column id=job_id title="Job" />
  <Column id=arm title="Arm" />
  <Column id=tasks title="Tasks" />
  <Column id=trials title="Trials" />
  <Column id=passed title="Passed" />
  <Column id=pass_rate title="Pass rate" fmt=pct1 />
  <Column id=ci_low title="95% low" fmt=pct1 />
  <Column id=ci_high title="95% high" fmt=pct1 />
  <Column id=timed_out title="Timed out" />
  <Column id=credits title="Credits" fmt=num0 />
  <Column id=credits_per_trial title="Credits per trial" fmt=num0 />
</DataTable>

Rates count trials. Intervals are Wilson 95% over trials. Credits leave out trials that the timeout killed. Only step-0 results are final evidence, and checkpoint forks are diagnosis. Paired comparisons by task come from `recorder/replay/report.py` and go to `reports/`.
