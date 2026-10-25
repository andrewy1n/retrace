---
title: Runs
sidebar: never
full_width: true
---

## Step-0 runs

```sql base
select r.job_id, r.arm, r.task_id, r.cost_credits, r.timed_out,
       r.repo_status, r.repo_regressed, r.acc_status, r.acc_at_start,
       s.assistant_turns, s.test_runs, s.whole_suite_runs, s.long_test_runs
from tiger.result_rows r
left join tiger.sessions s on s.session_id = r.session_id
where r.evidence_role = 'final'
```

```sql cost
select job_id, arm,
  count(distinct task_id)::int as tasks,
  count(*)::int as trials,
  avg(cost_credits) as credits_mean,
  median(cost_credits) as credits_median,
  avg(assistant_turns) as turns,
  avg(test_runs) as test_runs,
  avg(whole_suite_runs) as whole_suite_runs,
  avg(case when whole_suite_runs is null then null when whole_suite_runs > 0 then 1.0 else 0.0 end) as whole_suite_share,
  avg(long_test_runs) as long_test_runs,
  sum(case when timed_out then 1 else 0 end)::int as timed_out
from ${base}
group by 1, 2
order by job_id, arm
```

<DataTable data={cost} rows=20 wrapTitles=true emptySet=pass emptyMessage="No step-0 run yet.">
  <Column id=job_id title="Job" />
  <Column id=arm title="Arm" />
  <Column id=tasks title="Tasks" />
  <Column id=trials title="Trials" />
  <Column id=credits_mean title="Credits, mean" fmt=num0 />
  <Column id=credits_median title="Credits, median" fmt=num0 />
  <Column id=turns title="Assistant turns" fmt=num1 />
  <Column id=test_runs title="Test runs per trial" fmt=num1 />
  <Column id=whole_suite_runs title="Whole-suite runs per trial" fmt=num2 />
  <Column id=whole_suite_share title="Trials with a whole-suite run" fmt=pct1 />
  <Column id=long_test_runs title="Long test runs per trial" fmt=num1 />
  <Column id=timed_out title="Timed out" />
</DataTable>

Credits and behaviour are per trial. Credits include trials that the timeout killed. A whole-suite run is a test run with no path argument. A long test run takes more than 60 seconds. Behaviour comes from primitives, so a trial without primitives is not in those means.

```sql proxies
select job_id, arm,
  count(*)::int as trials,
  sum(case when repo_status = 'ok' then 1 else 0 end)::int as repo_ok,
  sum(case when repo_status = 'ok' and repo_regressed = 0 then 1 else 0 end)::int as repo_clean,
  sum(case when acc_at_start = 'fail' and acc_status <> 'error' then 1 else 0 end)::int as acc_usable,
  sum(case when acc_at_start = 'fail' and acc_status = 'pass' then 1 else 0 end)::int as acc_pass
from ${base}
group by 1, 2
order by job_id, arm
```

<DataTable data={proxies} rows=20 wrapTitles=true emptySet=pass emptyMessage="No step-0 run has proxies yet.">
  <Column id=job_id title="Job" />
  <Column id=arm title="Arm" />
  <Column id=trials title="Trials" />
  <Column id=repo_ok title="Repo tests ran" />
  <Column id=repo_clean title="0 regressed" />
  <Column id=acc_usable title="Acceptance usable" />
  <Column id=acc_pass title="Acceptance passing" />
</DataTable>

Repo tests count when the status is ok. "0 regressed" counts those trials that break no test that passed at the start. The acceptance check counts when it failed at the start and did not error.

## Checkpoint forks

```sql forks
select job_id, arm, count(*)::int as forks,
  sum(case when repo_status = 'ok' then 1 else 0 end)::int as repo_ok,
  sum(case when repo_status = 'ok' and repo_regressed = 0 then 1 else 0 end)::int as repo_clean,
  sum(case when acc_at_start = 'fail' and acc_status <> 'error' then 1 else 0 end)::int as acc_usable,
  sum(case when acc_at_start = 'fail' and acc_status = 'pass' then 1 else 0 end)::int as acc_pass,
  avg(cost_credits) as credits_mean,
  sum(cost_credits) as credits
from tiger.result_rows
where evidence_role = 'diagnosis'
group by 1, 2
order by job_id, arm
```

<DataTable data={forks} rows=20 wrapTitles=true emptySet=pass emptyMessage="No checkpoint fork has proxies yet.">
  <Column id=job_id title="Job" />
  <Column id=arm title="Arm" />
  <Column id=forks title="Forks" />
  <Column id=repo_ok title="Repo tests ran" />
  <Column id=repo_clean title="0 regressed" />
  <Column id=acc_usable title="Acceptance usable" />
  <Column id=acc_pass title="Acceptance passing" />
  <Column id=credits_mean title="Credits, mean" fmt=num0 />
  <Column id=credits title="Credits, total" fmt=num0 />
</DataTable>

Forks are diagnosis. They show proxies and credits only.
