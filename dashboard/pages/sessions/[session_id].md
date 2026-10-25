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

[Back to sessions](/sessions)

<BigValue data={head} value=task_id title="Task" />
<BigValue data={head} value=factory_credits fmt=num0 title="Credits" />
<BigValue data={head} value=assistant_turns title="Turns" />

{#if Array.from(head ?? [])[0]?.evidence_role === 'final'}
  <BigValue data={head} value=passed title="Passed" />
{:else}
  <BigValue data={head} value=repo_summary title="Repo tests" />
  <BigValue data={head} value=acc_summary title="Acceptance" />
{/if}

```sql calls
select position, tool_name, command_class, test_runner, duration_s, is_error, output_tokens_est
from tiger.calls
where session_id = '${params.session_id}'
order by position
```

<DataTable data={calls} rows=25 search=true />
