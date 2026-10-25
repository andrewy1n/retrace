with b as (
  select session_id,
         count(*) filter (where command_class = 'test')::int as test_runs,
         count(*) filter (where command_class = 'test' and path_arg_count = 0)::int as whole_suite_runs,
         count(*) filter (where command_class = 'test' and duration_s > 60)::int as long_test_runs,
         coalesce(sum(duration_s) filter (where command_class = 'test'), 0)::float8 as test_seconds
  from primitives_calls
  group by session_id
)
select s.session_id, s.task_id, s.job_id, s.trial, s.assistant_turns, s.tool_calls,
       s.factory_credits::float8 as factory_credits, s.timed_out,
       coalesce(b.test_runs, 0) as test_runs,
       coalesce(b.whole_suite_runs, 0) as whole_suite_runs,
       coalesce(b.long_test_runs, 0) as long_test_runs,
       coalesce(b.test_seconds, 0) as test_seconds,
       r.evidence_role, r.arm, r.model,
       r.proxies->'repo_tests'->>'status' as repo_status,
       (r.proxies->'repo_tests'->>'regressed')::int as repo_regressed,
       (r.proxies->'repo_tests'->>'passing_at_start')::int as repo_passing_at_start,
       r.proxies->'acceptance'->>'status' as acc_status,
       r.proxies->'acceptance'->>'at_start' as acc_at_start
from primitives_sessions s
left join b on b.session_id = s.session_id
left join replay_runs r on r.session_id = s.session_id
