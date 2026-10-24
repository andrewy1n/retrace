select job_id, task_id, checkpoint, arm, trial, evidence_role, passed::int as passed,
       cost_credits::float8 as cost_credits, coalesce(timed_out, false) as timed_out,
       model, droid_version, grader
from replay_results
