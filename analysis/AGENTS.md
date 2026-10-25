# Features and proposals

Kate owns this tree. Andrew owns capture, replay, and the dashboard.

`features/` holds the feature code. `proposals/` appears with its first source file. Do not edit the snapshot hook, the Droid SDK fork, or the grader.

## Session features

The pipeline has three layers (the Architecture tab of the project doc): primitives are facts about one tool call (Andrew), features are code over primitives and snapshots (Kate), and diagnoses are an agent's explanations built from features, citing `tool_call_id`s (Kate). This replaces labels. A session's feature record holds its hard signals, its cost features, and the legacy failure type below.

Feature code reads no grader output (the Grader section of the root `AGENTS.md`): not `passed`, not the gold or test patch, not the dataset's test lists. `analysis/features/session.py` drops `passed` and `grader` from each result on load, and `test_mocks.py` fails if a module in `analysis/features/` names them. Whether a run failed comes from the result's `proxies` instead.

A proxy fails when `repo_tests` ran (`status` `ok`) and a test that passes at the start commit regresses (`regressed` above 0), or when the acceptance check fails at the start commit and still fails with the patch. An acceptance check that passes at the start counts for nothing. When no proxy gave a verdict, the failure is unknown.

Hard signals come first, computed from the trace, the snapshots, and the proxies. The trace is an index of ids and snapshot refs. Tool input and output stay in the Droid session on the machine that recorded it. A session gets a signal's name in `hard_signals` when its rule holds:

- `proxy_failure`: a proxy fails, as above.
- `reverted_diff`: a file changes at one step, and a later snapshot restores that file's earlier content. Deleting a file the session created counts.
- `abandoned`: the final snapshot has no change at all against the start commit. An empty patch resolves no task.
- `code_survival`: under half of the lines the session added at any step are still in its final snapshot. The share is added lines in the final diff against the start commit, divided by added lines summed over the step diffs.
- `looping`: 5 or more steps in a row with the same `tool_name` and no change to the snapshot tree.

The start commit is the task repo's HEAD when the session starts, saved as `start_commit` in the session's directory (see `recorder/AGENTS.md`). In a SWE-bench image it sits on top of the dataset `base_commit` and changes only file modes, so a diff against `base_commit` lists every file. A step diff compares a snapshot with the one before it. The first step compares with the start commit. Compare trees, not commit ids, since every snapshot is a new commit. A test file matches the pattern in `reports/preregistration.md`. The thresholds of half and 5 are starting values, to be checked against the baseline.

The failure type is legacy from before the cost reframe. The cost path does not need it, and its rules assume Python test commands. Then a Signals-style detector assigns one failure type: `misread_requirement`, `wrong_assumption`, `skipped_verification`, `test_gaming`, `context_loss`, or `other`. Leave `other` as `other` until a human promotes it in the project doc.

Two failure types have rules in `reports/preregistration.md`, and those rules win over the detector. Check them in this order, and take the first that holds:

1. `test_gaming`: a proxy fails, and the final diff against the start commit removes or changes a line of a test file that existed at the start, or changes any `conftest.py`. Adding new tests, or editing a test file the session created, does not count. `repo_tests` runs the original test files, so weakened tests show up as regressions. The suspected step is the first step whose snapshot, diffed against the start commit, shows that change.
2. `skipped_verification`: no test command runs after the last step whose diff changes a non-test file. The suspected step is that last source-editing step. No proxy is needed.
3. Otherwise a session whose proxy fails goes to the detector. Until the detector exists, it is `other` with no suspected step.
4. Otherwise `failure_type` and `suspected_tool_call_id` are `null`.

When the failure is unknown, `pending` lists `proxy_failure`, and `test_gaming` too if the tests were weakened. The session's features are computed again once its result has proxies.

A step edits a file when its step diff changes that file, whatever its `tool_name`, since a shell command can edit too. A test command is a call whose primitives `command_class` is `test` (`runs/primitives/<session-id>.json`). It may be a call the trace lacks. Without primitives, as in some mocks, it is an `Execute` call whose transcript command runs `pytest`, `unittest`, `tox`, `manage.py test`, or a `runtests` script.

A suspected step is a replay checkpoint. Several tool calls can share one `message_id`, so tell Andrew which step a job names.

Call the detector Signals-style, and credit Factory Signals for the borrowed ideas: per-session facets, abstracted citations, a minimum step-count filter, severity and frequency thresholds for filing a ticket, and cross-checking friction against error logs. Use a cheap model.

Write `runs/features/<session-id>.json` with:

- `session_id`
- `hard_signals`, an array of the signal names above
- `failure_type`, or `null`
- `suspected_tool_call_id`, or `null`
- `pending`, the rules left undecided for lack of proxies (`[]` when none)
- `features`, the cost features below, or `null` without primitives

## Cost features

A cost feature is a count or a sum over the session's primitives calls, computed by `analysis/features/features.py`. A session has a feature when its value is above 0. The thresholds (2,000 tokens, 60 s) are starting values.

- `large_outputs`: calls whose `output_tokens_est` is over 2,000.
- `large_reads`: the same, for `Read` calls only.
- `carried_output_tokens`: the sum of `output_tokens_est × turns_after`, an estimate of tool output re-read on later turns.
- `repeated_calls`: calls with `repeats_earlier`.
- `whole_suite_tests`: test calls with `path_arg_count` 0.
- `slow_whole_suite_tests`: the same, running over 60 s.
- `tool_errors`: calls with `is_error`.
- `calls_after_last_edit`: calls after the last `edit`-class call.

`python analysis/features/summarize.py` prints, per dataset (from the job file), how many sessions have each feature and their mean credits with and without it. It reads only `runs/primitives` and `runs/jobs`. That is correlation. Only step-0 replay shows that removing a pattern saves credits. A promoted feature can be the target at Gate 3, and a proposal for it names it in `cost_pattern`.

`analysis/features/mock/expected.json` holds the expected feature record for each mock session. `python analysis/features/test_mocks.py` builds the mocks, computes their features, and compares. `python analysis/features/compute.py --sessions <dir> --tasks <dir>` prints feature records, and writes them only with `--out runs/features`. For real sessions, put the session folders under `runs/private/sessions/` and run `python analysis/features/fetch_tasks.py` first. It writes each traced task's `repo` and `base_commit`, Verified or Pro, to `runs/private/tasks/`. `compute.py` then loads each `snapshots.bundle` into a shared repo per upstream under `runs/private/repos/`. All three stay out of git.

Write `runs/tickets/<ticket-id>.json` with `ticket_id`, `friction_type`, `severity`, and `session_ids`. The ticket matches `contracts/friction-ticket.schema.json`. A ticket is the input to replay.

Features and diagnoses route work. They are not evidence. Spot-check about ten feature records before a target is selected.

Write diagnoses to `runs/diagnoses/`, citing `tool_call_id`s only, with the list of what stays unexplained. The directory appears with its first file.

## Jobs and proposals

Select the group by count times cost, and file it as a friction ticket. The hackathon pool is 20 to 40 tasks. When the group is too small to split, widen the task pool before writing jobs. A group that stays at 3 to 5 sessions is labeled small and uses monitoring plus rollback. Commit `splits/<group>.json` with `derivation`, `held_out`, and `regression` instance ids before studying the held-out tasks. About two thirds of the sessions derive the change and about one third are held out, from different repos. On Pro, `splits/pro_split.py` holds back 2 dev tasks per repo as the regression set, and they stay out of derivation (`splits/README.md`).

A job has a `start`, an arm, and a `model`. The arm is `control`, a hint string, or a path such as `analysis/proposals/<id>`. A `checkpoint` job names `tool_call_ids` and gives diagnosis. A `step0` job names `task_ids` and gives final evidence. The held-out and regression comparison uses `step0` jobs only. Keep the weakest hint that beats the no-hint control. Climb the hint ladder one step at a time: file pointer, fact, corrected assumption, clarified requirement. Record Factory credits. Cal Hacks has posted no hacker spending allotment. The Factory track prize is $2,000 cash, Factory credits, and swag, with no credit quantity.

Rank the harness change by how reliably it acts:

1. A blocking PreToolUse hook in `.factory/hooks.json` (exit code 2, or `permissionDecision` / `updatedInput`).
2. A skill (`.factory/skills/<name>/SKILL.md`), a tool, or a custom droid (`.factory/droids/`).
3. A setting or other context change.
4. An `AGENTS.md` rule. A hook that only prints a reminder counts as a rule.

A proposal directory is a harness overlay the runner copies onto the task checkout:

```
analysis/proposals/<id>/.factory/
analysis/proposals/<id>/AGENTS.md
```

`analysis/proposals/<id>/proposal.json` matches `contracts/proposed-change.schema.json` and stays in this repo. It names its target as exactly one of `failure_type` or `cost_pattern`. The lead example is a `.factory/hooks.json` guardrail that runs `.factory/hooks/block_test_edits.py` and blocks test edits. The proposal screen starts from the friction ticket and shows that guardrail. Use the smallest change the replay evidence supports. The leak check rejects task-specific paths, identifiers, error strings, and repo names. Freeze the directory before held-out and regression runs.

Held-out comparison is three arms, all fresh from step 0: unmodified Droid, a transcript-only rule, and the replay-derived change. A mid-session hint is diagnosis and stays out of that comparison.

Write the comparison, with its count, interval, and Factory credits, under `reports/`. The project doc does not get result tables. The Changes tab shows the before-and-after for the target failure type against untargeted types, the shipped-changes table, and rollback. Its numbers come from Tiger summaries.

Kate writes the acceptance checks (`contracts/acceptance-check.schema.json`) for dev tasks, never held-out ones before the candidate is frozen. `python analysis/features/acceptance.py prepare <task-id>` copies only the allowed inputs into a scratch folder outside the repo (default `<tmp>/retrace-acceptance/<task-id>/`): `instruction.md` (the session's `prompt.md` on Verified, the Harbor `instruction.md` read from the worker over SSH on Pro) and `repo/`, the tree at the session's `start_commit`. It refuses a held-out task. The author reads only that folder, writes `runs/acceptance/<task-id>/check.json` and `files/<path>`, and runs `check <task-id>... --draft`. `freeze <task-id>` sets `frozen_at` before any replay of the task, and `check` without `--draft` then passes. Andrew's `proxies.sh` confirms that each check fails at the start commit.
