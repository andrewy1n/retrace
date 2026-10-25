select s.session_id, s.task_id, s.job_id, s.trial, s.assistant_turns, s.tool_calls,
       s.factory_credits::float8 as factory_credits, s.timed_out,
       r.evidence_role, r.passed, r.grader, r.arm, r.model,
       r.proxies->'repo_tests'->>'status' as repo_status,
       (r.proxies->'repo_tests'->>'regressed')::int as repo_regressed,
       (r.proxies->'repo_tests'->>'passing_at_start')::int as repo_passing_at_start,
       r.proxies->'acceptance'->>'status' as acc_status,
       r.proxies->'acceptance'->>'at_start' as acc_at_start
from primitives_sessions s
left join replay_results r on r.session_id = s.session_id
