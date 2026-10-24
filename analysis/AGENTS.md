# Labeler and proposals

Kate owns this tree. Andrew owns capture, replay, and the dashboard.

`labeler/` and `proposals/` appear with their first source file. Do not edit the snapshot hook, the Droid SDK fork, or the grader.

## Labels

Hard signals come first, computed from the trace and the snapshots. The trace is an index of ids and snapshot refs. Tool input and output stay in the Droid session on the machine that recorded it. A session gets a signal's name in `hard_signals` when its rule holds:

- `failing_tests`: the SWE-bench grader fails the session's final patch.
- `reverted_diff`: a file changes at one step, and a later snapshot restores that file's earlier content. Deleting a file the session created counts.
- `abandoned`: the session fails, and its final snapshot has no change at all against the task's base commit.
- `code_survival`: under half of the lines the session added at any step are still in its final snapshot. The share is added lines in the final diff against the base commit, divided by added lines summed over the step diffs.
- `looping`: 5 or more steps in a row with the same `tool_name` and no change to the snapshot tree.
- `wrong_files`: the final diff against the base commit changes at least one non-test file, and none of the files in the task's gold patch. The gold patch is used for labeling only and never reaches the agent.

A step diff compares a snapshot with the one before it. The first step compares with the base commit. Compare trees, not commit ids, since every snapshot is a new commit. A test file matches the pattern in `reports/preregistration.md`. The thresholds of half and 5 are starting values, to be checked against the baseline.

Then a Signals-style detector assigns one failure type: `misread_requirement`, `wrong_assumption`, `skipped_verification`, `test_gaming`, `context_loss`, or `other`. Leave `other` as `other` until a human promotes it in the project doc.

Label the detector Signals-style, and credit Factory Signals for the borrowed ideas: per-session facets, abstracted citations, a minimum step-count filter, severity and frequency thresholds for filing a ticket, and cross-checking friction against error logs. Use a cheap model.

Write `runs/labels/<session-id>.json` with:

- `session_id`
- `hard_signals`, an array of the signal names above
- `failure_type`
- `suspected_tool_call_id`

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

`analysis/proposals/<id>/proposal.json` matches `contracts/proposed-change.schema.json` and stays in this repo. The lead example is a `.factory/hooks.json` guardrail that runs `.factory/hooks/block_test_edits.py` and blocks test edits. The proposal screen starts from the friction ticket and shows that guardrail. Use the smallest change the replay evidence supports. The leak check rejects task-specific paths, identifiers, error strings, and repo names. Freeze the directory before held-out and regression runs.

Held-out comparison is three arms, all fresh from step 0: unmodified Droid, a transcript-only rule, and the replay-derived change. A mid-session hint is diagnosis and stays out of that comparison.

Write the comparison, with its count, interval, and Factory credits, under `reports/`. The project doc does not get result tables. The Changes tab shows the before-and-after for the target failure type against untargeted types, the shipped-changes table, and rollback. Its numbers come from Tiger summaries.
