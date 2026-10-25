---
title: Session
---

```sql head
select *,
  case when repo_status = 'ok' then repo_regressed::int::varchar || ' regressed of ' || repo_passing_at_start::int::varchar
       when repo_status = 'no_tests' then 'no tests' when repo_status = 'error' then 'error' else 'not run' end as repo_summary,
  case when acc_status is not null then acc_status || ' (' || acc_at_start || ' at start)' else 'not run' end as acc_summary
from tiger.sessions where session_id = '${params.session_id}'
```

[Back to runs](/runs)

<BigValue data={head} value=task_id title="Task" />
<BigValue data={head} value=factory_credits fmt=num0 title="Credits" />
<BigValue data={head} value=assistant_turns title="Turns" />

<BigValue data={head} value=test_runs title="Test runs" />
<BigValue data={head} value=whole_suite_runs title="Whole-suite runs" />
<BigValue data={head} value=repo_summary title="Repo tests" />
<BigValue data={head} value=acc_summary title="Acceptance" />

```sql timeline
select position,
  case when command_class in ('test', 'run', 'read', 'search', 'edit') then command_class else 'other' end as class,
  coalesce(duration_s, 0) as seconds,
  coalesce(output_tokens_est, 0) as output_tokens,
  sum(coalesce(output_tokens_est, 0)) over (order by position) as cum_tokens
from tiger.calls
where session_id = '${params.session_id}'
order by position
```

<BarChart data={timeline} x=position y=seconds series=class type=stacked xType=value sort=false yFmt=num0
  seriesOrder={['test', 'run', 'read', 'search', 'edit', 'other']}
  seriesColors={{test: '#2a78d6', run: '#eb6834', read: '#1baf7a', search: '#eda100', edit: '#e87ba4', other: '#a1a1aa'}}
  title="Time per tool call" xAxisTitle="Tool call" yAxisTitle="Seconds" />

<Grid cols=2>

<BarChart data={timeline} x=position y=output_tokens series=class type=stacked xType=value sort=false yFmt=num0
  seriesOrder={['test', 'run', 'read', 'search', 'edit', 'other']}
  seriesColors={{test: '#2a78d6', run: '#eb6834', read: '#1baf7a', search: '#eda100', edit: '#e87ba4', other: '#a1a1aa'}}
  title="Tool output tokens per call" xAxisTitle="Tool call" />

<LineChart data={timeline} x=position y=cum_tokens xType=value yFmt=num0 yMin=0
  title="Tool output tokens, cumulative" xAxisTitle="Tool call" />

</Grid>

```sql calls
select position, tool_name, command_class, test_runner, path_arg_count, duration_s, is_error, exit_code, output_tokens_est
from tiger.calls
where session_id = '${params.session_id}'
order by position
```

<DataTable data={calls} rows=25 search=true />
