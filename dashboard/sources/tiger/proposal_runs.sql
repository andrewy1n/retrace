select r.job_id, r.task_id, r.arm, r.trial, r.session_id, r.model,
       r.cost_credits::float8 as cost_credits, coalesce(r.timed_out, false) as timed_out,
       r.proxies->'repo_tests'->>'status' as repo_status,
       (r.proxies->'repo_tests'->>'regressed')::int as repo_regressed,
       r.proxies->'acceptance'->>'status' as acc_status,
       r.proxies->'acceptance'->>'at_start' as acc_at_start,
       s.session_id is not null as has_primitives,
       coalesce(bool_or(c.test_runner is not null and c.path_arg_count = 0 and coalesce(c.duration_s, 0) > 60), false) as signal_whole_suite_tests
from replay_runs r
left join primitives_sessions s on s.session_id = r.session_id
left join primitives_calls c on c.session_id = s.session_id
where r.evidence_role = 'final' and r.arm in ('control', 'candidate')
group by r.job_id, r.task_id, r.arm, r.trial, r.session_id, r.model, r.cost_credits, r.timed_out, r.proxies, s.session_id
