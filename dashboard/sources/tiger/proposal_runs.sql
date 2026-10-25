with execs as (
  select session_id,
         count(*) filter (where is_error and prev_error) >= 3 as signal_shell_error_streak
  from (
    select session_id, is_error,
           lag(is_error) over (partition by session_id order by position) as prev_error
    from primitives_calls
    where tool_name = 'Execute'
  ) e
  group by session_id
),
rereads as (
  select session_id,
         count(*) filter (where prior) >= 3 as signal_file_rereads
  from (
    select session_id,
           files[1] = any(array_remove(
             array_agg(files[1]) over (
               partition by session_id
               order by position
               rows between unbounded preceding and 1 preceding
             ),
             null::text
           )) as prior
    from primitives_calls
    where tool_name = 'Read' and cardinality(files) > 0
  ) r
  group by session_id
)
select r.job_id, r.task_id, r.arm, r.trial, r.session_id, r.model,
       r.cost_credits::float8 as cost_credits, coalesce(r.timed_out, false) as timed_out,
       r.proxies->'repo_tests'->>'status' as repo_status,
       (r.proxies->'repo_tests'->>'regressed')::int as repo_regressed,
       r.proxies->'acceptance'->>'status' as acc_status,
       r.proxies->'acceptance'->>'at_start' as acc_at_start,
       s.session_id is not null as has_primitives,
       sum(c.duration_s)::float8 as tool_seconds,
       s.assistant_turns,
       (array_agg(c.exit_code order by c.position desc) filter (where c.test_runner is not null))[1] = 0 as last_test_pass,
       coalesce(bool_or(c.test_runner is not null and c.path_arg_count = 0 and coalesce(c.duration_s, 0) > 60), false) as signal_whole_suite_tests,
       coalesce(min(c.position) filter (where c.command_class = 'edit'), count(c.position)) > 12 as signal_calls_before_first_edit,
       coalesce(e.signal_shell_error_streak, false) as signal_shell_error_streak,
       coalesce(bool_or(c.command_class = 'search' and c.files = array['.']::text[] and coalesce(c.output_tokens_est, 0) > 2000), false) as signal_large_root_searches,
       coalesce(rr.signal_file_rereads, false) as signal_file_rereads
from replay_runs r
left join primitives_sessions s on s.session_id = r.session_id
left join primitives_calls c on c.session_id = s.session_id
left join execs e on e.session_id = s.session_id
left join rereads rr on rr.session_id = s.session_id
where r.evidence_role = 'final' and r.arm in ('control', 'candidate')
group by r.job_id, r.task_id, r.arm, r.trial, r.session_id, r.model, r.cost_credits, r.timed_out, r.proxies, s.session_id, s.assistant_turns,
         e.signal_shell_error_streak, rr.signal_file_rereads
