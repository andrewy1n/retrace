---
title: Results
sidebar: never
full_width: true
---

## Final trials

```sql arms
with t as (
  select job_id, arm, count(distinct task_id)::int as tasks, count(*)::double as n, sum(passed)::double as k,
         sum(case when timed_out then 1 else 0 end)::int as timed_out,
         sum(case when timed_out then 0 else cost_credits end) as credits,
         sum(case when timed_out then 0 else 1 end)::double as m
  from tiger.result_rows
  where evidence_role = 'final'
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

Rates count trials. Intervals are Wilson 95% over trials. Credits leave out trials that the timeout killed. Only step-0 results are final evidence. Paired comparisons by task come from `recorder/replay/report.py` and go to `reports/`.

## Proxy agreement

```sql agreement
with f as (
  select passed,
    repo_status = 'ok' as repo_usable, coalesce(repo_regressed = 0, false) as repo_pred,
    acc_at_start = 'fail' and acc_status <> 'error' as acc_usable, coalesce(acc_status = 'pass', false) as acc_pred
  from tiger.result_rows
  where evidence_role = 'final'
), u as (
  select 'Repo tests' as proxy, 'Regressed = 0' as predicts_pass, repo_pred as pred, passed from f where repo_usable
  union all
  select 'Acceptance check', 'Check passes', acc_pred, passed from f where acc_usable
), c as (
  select proxy, predicts_pass,
    count(*)::int as n,
    sum(case when pred and passed = 1 then 1 else 0 end)::int as pass_pass,
    sum(case when pred and passed = 0 then 1 else 0 end)::int as pass_fail,
    sum(case when not pred and passed = 1 then 1 else 0 end)::int as fail_pass,
    sum(case when not pred and passed = 0 then 1 else 0 end)::int as fail_fail
  from u
  group by 1, 2
)
select *, (pass_pass + fail_fail)::double / n as agreement
from c
order by proxy
```

<DataTable data={agreement} wrapTitles=true>
  <Column id=proxy title="Proxy" />
  <Column id=predicts_pass title="Predicts pass when" />
  <Column id=n title="Usable trials" />
  <Column id=pass_pass title="Proxy pass, grader pass" />
  <Column id=pass_fail title="Proxy pass, grader fail" />
  <Column id=fail_pass title="Proxy fail, grader pass" />
  <Column id=fail_fail title="Proxy fail, grader fail" />
  <Column id=agreement title="Agreement" fmt=pct1 />
</DataTable>

Agreement with the dataset grader on final trials. For verification only; the improvement loop never reads it. Repo tests are usable when the status is ok. The acceptance check is usable when it failed at the start and did not error. A proxy is not tuned against this table.

## Checkpoint forks

```sql forks
select job_id, arm, count(*)::int as forks,
  sum(case when repo_status = 'ok' then 1 else 0 end)::int as repo_ok,
  sum(case when repo_status = 'ok' and repo_regressed = 0 then 1 else 0 end)::int as repo_clean,
  sum(case when acc_at_start = 'fail' and acc_status <> 'error' then 1 else 0 end)::int as acc_usable,
  sum(case when acc_at_start = 'fail' and acc_status = 'pass' then 1 else 0 end)::int as acc_pass,
  sum(cost_credits) as credits
from tiger.result_rows
where evidence_role = 'diagnosis'
group by 1, 2
order by job_id, arm
```

<DataTable data={forks} rows=20 wrapTitles=true>
  <Column id=job_id title="Job" />
  <Column id=arm title="Arm" />
  <Column id=forks title="Forks" />
  <Column id=repo_ok title="Repo tests ran" />
  <Column id=repo_clean title="0 regressed" />
  <Column id=acc_usable title="Acceptance usable" />
  <Column id=acc_pass title="Acceptance pass" />
  <Column id=credits title="Credits" fmt=num0 />
</DataTable>

Forks have no pass or fail. They show the proxies only. Forks are diagnosis, not final evidence.
