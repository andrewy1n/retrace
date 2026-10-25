---
title: Runs
sidebar: never
full_width: true
---

```sql jobs
select distinct job_id from tiger.sessions order by job_id
```

<Dropdown name=job data={jobs} value=job_id multiple=true selectAllByDefault=true title="Job" />

```sql sessions_f
select *,
  case when job_id like 'pro-%' then 'SWE-bench Pro' else 'SWE-bench Verified' end as benchmark,
  coalesce(arm, 'control') as arm_label
from tiger.sessions
where job_id in ${inputs.job.value}
```

```sql summary
select
  count(*) as sessions,
  sum(factory_credits) as credits,
  median(factory_credits) as median_credits,
  median(assistant_turns) as median_turns,
  avg(case when whole_suite_runs > 0 then 1.0 else 0.0 end) as whole_suite_share
from ${sessions_f}
```

<BigValue data={summary} value=sessions title="Sessions" />
<BigValue data={summary} value=credits fmt=num0 title="Factory credits" />
<BigValue data={summary} value=median_credits fmt=num0 title="Median credits per session" />
<BigValue data={summary} value=median_turns fmt=num0 title="Median assistant turns" />
<BigValue data={summary} value=whole_suite_share fmt=pct0 title="Sessions with a whole-suite run" />

## Cost

```sql pareto
select
  row_number() over (order by factory_credits desc) * 1.0 / count(*) over () as session_share,
  sum(factory_credits) over (order by factory_credits desc rows between unbounded preceding and current row)
    / sum(factory_credits) over () as credit_share
from ${sessions_f}
order by session_share
```

```sql top_decile
select max(credit_share) as share from ${pareto} where session_share <= 0.1
```

The most expensive 10% of sessions use <Value data={top_decile} column=share fmt=pct0 /> of the credits.

<Grid cols=2>

<LineChart data={pareto} x=session_share y=credit_share xType=value xFmt=pct0 xMax=1 yFmt=pct0 yMin=0 yMax=1
  title="Cumulative share of credits, most expensive sessions first"
  xAxisTitle="Share of sessions" yAxisTitle="Share of credits" />

<ScatterPlot data={sessions_f} x=assistant_turns y=factory_credits series=benchmark yFmt=num0 yMin=0
  seriesColors={{'SWE-bench Verified': '#2a78d6', 'SWE-bench Pro': '#eb6834'}}
  tooltipTitle=session_id
  title="Credits per session against assistant turns"
  xAxisTitle="Assistant turns" yAxisTitle="Factory credits" />

</Grid>

```sql by_job
select job_id, arm_label as arm, avg(factory_credits) as mean_credits
from ${sessions_f}
group by 1, 2
order by 1, 2
```

<BarChart data={by_job} x=job_id y=mean_credits series=arm type=stacked swapXY=true yFmt=num0
  seriesColors={{control: '#2a78d6', candidate: '#eb6834', hint: '#1baf7a'}}
  title="Mean credits per session, by job and arm" />

## Where tool output and time go

```sql by_class
select s.job_id,
  case when c.command_class in ('test', 'run', 'read', 'search', 'edit') then c.command_class else 'other' end as class,
  sum(c.output_tokens_est) as output_tokens,
  sum(coalesce(c.duration_s, 0)) as seconds
from tiger.calls c
join ${sessions_f} s on s.session_id = c.session_id
group by 1, 2
order by 1
```

<BarChart data={by_class} x=job_id y=output_tokens series=class type=stacked100 swapXY=true yFmt=pct0 chartAreaHeight=200
  seriesOrder={['test', 'run', 'read', 'search', 'edit', 'other']}
  seriesColors={{test: '#2a78d6', run: '#eb6834', read: '#1baf7a', search: '#eda100', edit: '#e87ba4', other: '#a1a1aa'}}
  title="Tool output tokens, by command class" />

<BarChart data={by_class} x=job_id y=seconds series=class type=stacked100 swapXY=true yFmt=pct0 chartAreaHeight=200
  seriesOrder={['test', 'run', 'read', 'search', 'edit', 'other']}
  seriesColors={{test: '#2a78d6', run: '#eb6834', read: '#1baf7a', search: '#eda100', edit: '#e87ba4', other: '#a1a1aa'}}
  title="Tool call time, by command class" />

Tool output stays in the context, so a large output early in a session is read again on every later turn. Time includes test runs that wait on slow suites.

## Test behaviour

```sql tests_by_job
select job_id, 'Whole suite' as kind, avg(whole_suite_runs) as runs from ${sessions_f} group by 1
union all
select job_id, 'Scoped' as kind, avg(test_runs - whole_suite_runs) as runs from ${sessions_f} group by 1
order by 1
```

```sql long_by_job
select job_id, avg(case when long_test_runs > 0 then 1.0 else 0.0 end) as share
from ${sessions_f}
group by 1
order by 1
```

<BarChart data={tests_by_job} x=job_id y=runs series=kind type=stacked swapXY=true yFmt=num1 chartAreaHeight=200
  seriesOrder={['Whole suite', 'Scoped']}
  seriesColors={{'Whole suite': '#eb6834', 'Scoped': '#2a78d6'}}
  title="Test runs per session" />

<BarChart data={long_by_job} x=job_id y=share swapXY=true yFmt=pct0 yMax=1 fillColor='#2a78d6' chartAreaHeight=200
  title="Sessions with a test run over 60 seconds" />

A whole-suite run is a test command with no path argument. These numbers come from primitives.

## Proxies on step-0 runs

```sql repo_status
select job_id as run,
  case when repo_status = 'ok' and repo_regressed = 0 then '0 regressed'
       when repo_status = 'ok' then 'Regressed'
       when repo_status = 'no_tests' then 'No tests found'
       else 'Error' end as status,
  count(*) as trials
from tiger.result_rows
where evidence_role = 'final' and repo_status is not null and job_id in ${inputs.job.value}
group by 1, 2
order by 1
```

```sql acc_status
select job_id as run,
  case when acc_at_start = 'fail' and acc_status = 'pass' then 'Passes'
       when acc_at_start = 'fail' and acc_status = 'fail' then 'Fails'
       else 'No verdict' end as status,
  count(*) as trials
from tiger.result_rows
where evidence_role = 'final' and acc_status is not null and job_id in ${inputs.job.value}
group by 1, 2
order by 1
```

<BarChart data={repo_status} x=run y=trials series=status type=stacked swapXY=true labels=true yAxisLabels=false yGridlines=false chartAreaHeight=120
  seriesOrder={['0 regressed', 'Regressed', 'No tests found', 'Error']}
  seriesColors={{'0 regressed': '#0ca30c', 'Regressed': '#d03b3b', 'No tests found': '#a1a1aa', 'Error': '#fab219'}}
  emptySet=pass emptyMessage="No step-0 run has repo-test proxies yet."
  title="Repo tests that passed at the start, with the patch" />

<BarChart data={acc_status} x=run y=trials series=status type=stacked swapXY=true labels=true yAxisLabels=false yGridlines=false chartAreaHeight=120
  seriesOrder={['Passes', 'Fails', 'No verdict']}
  seriesColors={{'Passes': '#0ca30c', 'Fails': '#d03b3b', 'No verdict': '#a1a1aa'}}
  emptySet=pass emptyMessage="No step-0 run has an acceptance check yet."
  title="Acceptance check with the patch" />

The acceptance check counts only when it fails at the start commit. Proxies need no hidden tests, so a production system has them too.

## Sessions

```sql sessions
select
  case when length(session_id) > 50 then regexp_replace(replace(session_id, 'instance_', ''), '-([0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f])[0-9a-f]+(-v[0-9a-f]+)?(-[0-9])$', '-\\1\\3') else session_id end as session_id,
  job_id, arm_label as arm, trial::int as trial, assistant_turns, tool_calls, factory_credits,
  test_runs, whole_suite_runs, long_test_runs, test_seconds,
  case when repo_status = 'ok' then repo_regressed::int::varchar || ' regressed of ' || repo_passing_at_start::int::varchar
       when repo_status = 'no_tests' then 'no tests' when repo_status = 'error' then 'error' end as repo_tests,
  case when acc_status is not null then acc_status || ' (' || acc_at_start || ' at start)' end as acceptance,
  '/sessions/' || session_id as link
from ${sessions_f}
order by factory_credits desc
```

<DataTable data={sessions} link=link rows=10 search=true wrapTitles=true>
  <Column id=session_id />
  <Column id=job_id />
  <Column id=arm />
  <Column id=trial />
  <Column id=assistant_turns title="Turns" />
  <Column id=tool_calls title="Tool calls" />
  <Column id=factory_credits fmt=num0 contentType=bar barColor='#cde2fb' title="Credits" />
  <Column id=test_runs title="Test runs" />
  <Column id=whole_suite_runs title="Whole-suite runs" />
  <Column id=long_test_runs title="Long test runs" />
  <Column id=repo_tests title="Repo tests" />
  <Column id=acceptance />
</DataTable>

Select a session to see each tool call.

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
