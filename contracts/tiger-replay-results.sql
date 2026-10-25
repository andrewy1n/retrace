create table replay_results (
  job_id          text    not null,
  task_id         text    not null,
  checkpoint      text    not null,
  arm             text    not null check (arm in ('control', 'hint', 'candidate')),
  trial           integer not null check (trial >= 1),
  session_id      text,
  tool_call_id    text,
  model           text    not null,
  droid_version   text    not null,
  stop_mode       text    not null check (stop_mode in ('next_user_turn', 'reuse_reply', 'simulated_user')),
  passed          boolean,
  grader          text    check (grader in ('swebench', 'swebench_pro')),
  evidence_role   text    not null check (evidence_role in ('diagnosis', 'final')),
  cost_credits    numeric not null check (cost_credits >= 0),
  timed_out       boolean,
  proxies         jsonb,
  repo_sha        text,
  worker_id       text,
  artifact_key    text,
  recorded_at     timestamptz not null default now(),
  primary key (job_id, task_id, checkpoint, arm, trial),
  check ((evidence_role = 'diagnosis') = (tool_call_id is not null)),
  check ((evidence_role = 'final') = (passed is not null)),
  check ((evidence_role = 'final') = (grader is not null)),
  check (checkpoint = coalesce(tool_call_id, 'step0'))
);

grant select, insert, update on replay_results to retrace_worker;
grant select on replay_results to retrace_dashboard;
