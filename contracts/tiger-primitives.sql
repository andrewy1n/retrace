create table primitives_sessions (
  session_id            text    primary key,
  task_id               text    not null,
  job_id                text    not null,
  trial                 integer not null check (trial >= 1),
  harness               text    not null,
  assistant_turns       integer not null check (assistant_turns >= 0),
  tool_calls            integer not null check (tool_calls >= 0),
  timed_out             boolean not null,
  input_tokens          integer not null check (input_tokens >= 0),
  output_tokens         integer not null check (output_tokens >= 0),
  cache_creation_tokens integer not null check (cache_creation_tokens >= 0),
  cache_read_tokens     integer not null check (cache_read_tokens >= 0),
  thinking_tokens       integer not null check (thinking_tokens >= 0),
  factory_credits       numeric not null check (factory_credits >= 0),
  recorded_at           timestamptz not null default now()
);

create table primitives_calls (
  session_id        text    not null references primitives_sessions (session_id),
  tool_call_id      text    not null,
  position          integer not null check (position >= 0),
  turn              integer not null check (turn >= 0),
  tool_name         text    not null,
  command_class     text    not null check (command_class in ('test', 'run', 'read', 'search', 'edit', 'vcs', 'install', 'sleep_or_wait', 'other')),
  test_runner       text    check (test_runner in ('pytest', 'django_runtests', 'sympy_bin_test', 'unittest', 'go_test', 'ansible_test')),
  path_arg_count    integer check (path_arg_count >= 0),
  background        boolean not null,
  duration_s        numeric check (duration_s >= 0),
  is_error          boolean,
  exit_code         integer,
  files             text[]  not null,
  output_chars      integer check (output_chars >= 0),
  output_tokens_est integer check (output_tokens_est >= 0),
  turns_after       integer not null check (turns_after >= 0),
  repeats_earlier   boolean not null,
  primary key (session_id, tool_call_id)
);

grant select, insert, update on primitives_sessions to retrace_worker;
grant select on primitives_sessions to retrace_dashboard;
grant select, insert, update on primitives_calls to retrace_worker;
grant select on primitives_calls to retrace_dashboard;
