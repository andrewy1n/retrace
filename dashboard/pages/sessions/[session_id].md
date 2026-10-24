---
title: Session
---

```sql head
select * from tiger.sessions where session_id = '${params.session_id}'
```

[Back to sessions](/sessions)

<BigValue data={head} value=task_id title="Task" />
<BigValue data={head} value=factory_credits fmt=num0 title="Credits" />
<BigValue data={head} value=assistant_turns title="Turns" />
<BigValue data={head} value=passed title="Passed" />

```sql calls
select position, tool_name, command_class, test_runner, duration_s, is_error, output_tokens_est
from tiger.calls
where session_id = '${params.session_id}'
order by position
```

<DataTable data={calls} rows=25 search=true />
