# Labeler and proposals

Kate owns this tree. Andrew owns capture, replay, and the dashboard.

`labeler/` and `proposals/` appear with their first source file. Do not edit the snapshot hook, the Droid SDK fork, or the grader.

## Labels

Hard signals come first, computed from the trace and the snapshots. The trace is an index of ids and snapshot refs. Tool input and output stay in the Droid session on the machine that recorded it. A session gets a signal's name in `hard_signals` when its rule holds:

- `failing_tests`: the dataset's grader (SWE-bench or SWE-bench Pro) fails the session's final patch.
- `reverted_diff`: a file changes at one step, and a later snapshot restores that file's earlier content. Deleting a file the session created counts.
- `abandoned`: the session fails, and its final snapshot has no change at all against the start commit.
- `code_survival`: under half of the lines the session added at any step are still in its final snapshot. The share is added lines in the final diff against the start commit, divided by added lines summed over the step diffs.
- `looping`: 5 or more steps in a row with the same `tool_name` and no change to the snapshot tree.
- `wrong_files`: the final diff against the start commit changes at least one non-test file, and none of the files in the task's gold patch. The gold patch is used for labeling only and never reaches the agent.

The start commit is the task repo's HEAD when the session starts, saved as `start_commit` in the session's directory (see `recorder/AGENTS.md`). In a SWE-bench image it sits on top of the dataset `base_commit` and changes only file modes, so a diff against `base_commit` lists every file. A step diff compares a snapshot with the one before it. The first step compares with the start commit. Compare trees, not commit ids, since every snapshot is a new commit. A test file matches the pattern in `reports/preregistration.md`. The thresholds of half and 5 are starting values, to be checked against the baseline.

Then a Signals-style detector assigns one failure type: `misread_requirement`, `wrong_assumption`, `skipped_verification`, `test_gaming`, `context_loss`, or `other`. Leave `other` as `other` until a human promotes it in the project doc.

Two failure types have rules in `reports/preregistration.md`, and those rules win over the detector. Check them in this order, and take the first that holds:

1. `test_gaming`: the session fails, and its final diff against the start commit removes or changes a line of a test file that existed at the start, or changes any `conftest.py`. Adding new tests, or editing a test file the session created, does not count. The suspected step is the first step whose snapshot, diffed against the start commit, shows that change.
2. `skipped_verification`: no test command runs after the last step whose diff changes a non-test file. The suspected step is that last source-editing step.
3. Otherwise a failed session goes to the detector. Until the detector exists, it is `other` with no suspected step.
4. Otherwise `failure_type` and `suspected_tool_call_id` are `null`.

A step edits a file when its step diff changes that file, whatever its `tool_name`, since a shell command can edit too. A test command is a call whose primitives `command_class` is `test` (`runs/primitives/<session-id>.json`). It may be a call the trace lacks. Without primitives, as in some mocks, it is an `Execute` call whose transcript command runs `pytest`, `unittest`, `tox`, `manage.py test`, or a `runtests` script.

A suspected step is a replay checkpoint. Several tool calls can share one `message_id`, so tell Andrew which step a job names.

Label the detector Signals-style, and credit Factory Signals for the borrowed ideas: per-session facets, abstracted citations, a minimum step-count filter, severity and frequency thresholds for filing a ticket, and cross-checking friction against error logs. Use a cheap model.

Write `runs/labels/<session-id>.json` with:

- `session_id`
- `hard_signals`, an array of the signal names above
- `failure_type`, or `null`
- `suspected_tool_call_id`, or `null`
- `features`, the cost features below, or `null` without primitives

## Cost features

A cost feature is a count or a sum over the session's primitives calls, computed by `analysis/labeler/features.py`. A session has a feature when its value is above 0. The thresholds (2,000 tokens, 60 s) are starting values.

- `large_outputs`: calls whose `output_tokens_est` is over 2,000.
- `large_reads`: the same, for `Read` calls only.
- `carried_output_tokens`: the sum of `output_tokens_est × turns_after`, an estimate of tool output re-read on later turns.
- `repeated_calls`: calls with `repeats_earlier`.
- `whole_suite_tests`: test calls with `path_arg_count` 0.
- `slow_whole_suite_tests`: the same, running over 60 s.
- `tool_errors`: calls with `is_error`.
- `calls_after_last_edit`: calls after the last `edit`-class call.

`python analysis/labeler/summarize.py` prints, per grader, how many sessions have each feature and their mean credits with and without it. It reads only `runs/primitives` and `runs/results`. That is correlation. Only step-0 replay shows that removing a pattern saves credits. A promoted feature can be the target at Gate 3, and a proposal for it names it in `cost_pattern`.

`analysis/labeler/mock/expected.json` holds the expected label for each mock session. `python analysis/labeler/test_mocks.py` builds the mocks, labels them, and compares. `python analysis/labeler/label.py --sessions <dir> --tasks <dir>` prints labels, and writes them only with `--out`. For real sessions, put the session folders under `runs/private/sessions/` and run `python analysis/labeler/fetch_tasks.py` first. It writes the gold files for every traced task, Verified or Pro, to `runs/private/tasks/`. The labeler then loads each `snapshots.bundle` into a shared repo per upstream under `runs/private/repos/`. All three stay out of git.

Write `runs/tickets/<ticket-id>.json` with `ticket_id`, `friction_type`, `severity`, and `session_ids`. The ticket matches `contracts/friction-ticket.schema.json`. A ticket is the input to replay.

Labels route work. They are not evidence. Spot-check about ten labels before a group is selected.

## Jobs and proposals

Select the group by count times cost, and file it as a friction ticket. The hackathon pool is 20 to 40 tasks. When the group is too small to split, widen the task pool before writing jobs. A group that stays at 3 to 5 sessions is labeled small and uses monitoring plus rollback. Commit `splits/<group>.json` with `derivation`, `held_out`, and `regression` instance ids before studying the held-out tasks. About two thirds of the sessions derive the change and about one third are held out, from different repos. The regression set is about ten good past sessions, including legitimate test edits.

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
