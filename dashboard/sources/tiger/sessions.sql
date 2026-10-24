select s.session_id, s.task_id, s.job_id, s.trial, s.assistant_turns, s.tool_calls,
       s.factory_credits::float8 as factory_credits, s.timed_out,
       r.passed, r.grader, r.arm, r.model
from primitives_sessions s
left join replay_results r on r.session_id = s.session_id
