select job_id, task_id, checkpoint, arm, trial, evidence_role, session_id,
       cost_credits::float8 as cost_credits, coalesce(timed_out, false) as timed_out,
       model, droid_version,
       proxies->'repo_tests'->>'status' as repo_status,
       (proxies->'repo_tests'->>'regressed')::int as repo_regressed,
       (proxies->'repo_tests'->>'passing_at_start')::int as repo_passing_at_start,
       (proxies->'repo_tests'->>'newly_passing')::int as repo_newly_passing,
       jsonb_array_length(proxies->'repo_tests'->'selected') as repo_selected,
       proxies->'acceptance'->>'status' as acc_status,
       proxies->'acceptance'->>'at_start' as acc_at_start
from replay_runs
