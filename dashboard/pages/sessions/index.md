---
title: Sessions
sidebar: never
full_width: true
---

```sql jobs
select distinct job_id from tiger.sessions order by job_id
```

<Dropdown name=job data={jobs} value=job_id multiple=true selectAllByDefault=true title="Job" />

```sql summary
select
  count(*) as sessions,
  sum(factory_credits) as credits,
  median(assistant_turns) as median_turns,
  avg(case when whole_suite_runs > 0 then 1.0 else 0.0 end) as whole_suite_share
from tiger.sessions
where job_id in ${inputs.job.value}
```

<BigValue data={summary} value=sessions title="Sessions" />
<BigValue data={summary} value=credits fmt=num0 title="Factory credits" />
<BigValue data={summary} value=median_turns fmt=num0 title="Median turns" />
<BigValue data={summary} value=whole_suite_share fmt=pct1 title="Sessions with a whole-suite run" />

```sql by_job
select job_id, 'Trial ' || trial::int as trial, avg(factory_credits) as mean_credits
from tiger.sessions
where job_id in ${inputs.job.value}
group by 1, 2
order by 1, 2
```

<BarChart data={by_job} x=job_id y=mean_credits series=trial type=grouped title="Mean credits per trial" yFmt=num0 />

```sql sessions
select
  case when length(session_id) > 50 then regexp_replace(replace(session_id, 'instance_', ''), '-([0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f])[0-9a-f]+(-v[0-9a-f]+)?(-[0-9])$', '-\\1\\3') else session_id end as session_id,
  case when length(task_id) > 50 then regexp_replace(replace(task_id, 'instance_', ''), '-([0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f])[0-9a-f]+(-v[0-9a-f]+)?$', '-\\1') else task_id end as task_id,
  job_id, trial::int as trial, assistant_turns, tool_calls, factory_credits,
  test_runs, whole_suite_runs, long_test_runs, test_seconds,
  case when repo_status = 'ok' then repo_regressed::int::varchar || ' regressed of ' || repo_passing_at_start::int::varchar
       when repo_status = 'no_tests' then 'no tests' when repo_status = 'error' then 'error' end as repo_tests,
  case when acc_status is not null then acc_status || ' (' || acc_at_start || ' at start)' end as acceptance,
  '/sessions/' || session_id as link
from tiger.sessions
where job_id in ${inputs.job.value}
order by factory_credits desc
```

<DataTable data={sessions} link=link rows=15 search=true wrapTitles=true>
  <Column id=session_id />
  <Column id=task_id />
  <Column id=job_id />
  <Column id=trial />
  <Column id=assistant_turns />
  <Column id=tool_calls />
  <Column id=factory_credits fmt=num0 />
  <Column id=test_runs title="Test runs" />
  <Column id=whole_suite_runs title="Whole-suite runs" />
  <Column id=long_test_runs title="Long test runs" />
  <Column id=test_seconds title="Test seconds" fmt=num0 />
  <Column id=repo_tests title="Repo tests" />
  <Column id=acceptance />
</DataTable>
