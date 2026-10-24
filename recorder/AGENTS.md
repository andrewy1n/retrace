# Recorder and replay

Andrew owns this tree and the dashboard. Kate owns labels, jobs, proposals, and the Tiger schema.

`capture/` is the Droid PostToolUse hook. `replay/` is the runner. Create each directory with its first source file. Claude Code is an optional adapter. Cut the extra example cases first, then this adapter.

## Capture

After every tool call, a `.factory/hooks.json` PostToolUse hook runs `capture/snapshot.sh` and stores the printed commit id as `snapshot_ref`. The snapshot includes untracked files and omits ignored files. It uses a temporary index, so the working tree, the index, and the branch stay unchanged. It always prints a commit, even on a clean tree. Each commit is pinned under `refs/retrace/` so `git gc` keeps it. Keep the task repo's `.git` and `~/.factory` on volumes that outlive the container. The trace step also stores `tool_call_id`, `message_id`, and `tool_name`. It does not store tool input or output. The conversation stays in the Droid session.

The hook sees the tree and may see `message_id`. The SDK stream has the tool-use id and the message id `session.rewind` takes. Capture both and join them onto the step. Tolerate schema drift. Write `runs/traces/<session-id>.json` so it validates against `contracts/trace.schema.json`. Skip sessions whose outcome depends on state outside the repo. Private sessions go in `runs/private/` and stay uncommitted.

Store `harness_session_id` as the id `resumeSession` accepts. For a SWE-bench task, `task_id` is the instance id. The demo `harness` value is `droid`.

Droid session files are JSONL at `~/.factory/sessions/<cwd-slug>/<id>.jsonl`. That layout comes from third-party parsers and is unverified.

## Rewind

`session.rewind` restores only the file snapshots passed in `filesToRestore`. Those objects come from `getRewindInfo` and carry `filePath`, `contentHash`, and `size`. `filesToDelete` entries are `{ filePath }`. Evicted files are not restored. The call returns a successor session, and that successor is the fork. `forkTitle` is required. `session.fork()` copies the current conversation and does not rewind.

Checked against `@factory/droid-sdk` 0.10.0 and the TypeScript SDK docs on 2026-10-22. A live rewind is not required to confirm this. Git snapshots stay the source of truth. After rewind, run `replay/restore.sh <snapshot_ref>` on the checkout. It restores the working tree, removes files created later, resets the index and `HEAD` to the snapshot's parent, and keeps ignored files.

If rewind fails, restore the snapshot and start a fresh session seeded with the transcript prefix from the Droid session. That fallback is unverified.

## Replay

A `checkpoint` job resumes the Droid session, rewinds to the step's `message_id`, restores `snapshot_ref`, runs the arm, and writes one result file per trial. A `step0` job starts each task in `task_ids` fresh at its base commit, with the arm installed. Record `model` and `droid --version` on every result. It does not choose checkpoints, write hints, label failures, or turn a hint into a harness change.

Call `resumeSession(harness_session_id)`, then `getRewindInfo({ messageId })`, then `session.rewind({ messageId, filesToRestore, filesToDelete, forkTitle })`. Continue on the successor. `resumeSession` pins the saved working directory, so trials on that checkout run one at a time until a directory change is verified.

Read cost from each turn's `tokenUsage.factoryCredits` and sum those into `cost_credits`. The field is optional and covers one `stream()` call. `TokenUsageUpdate` is the session total and can include the prefix. Cap the job at `budget_credits`. Cal Hacks has posted no hacker spending allotment. The Factory track prize is $2,000 cash, Factory credits, and swag, with no credit quantity.

Stop modes are `next_user_turn`, `reuse_reply`, and `simulated_user`. Record the mode actually used. The first two carry full evidence weight while the branch still matches. `simulated_user` is weaker and stays labeled as such. The text of the no-hint control is unset.

A `checkpoint` trial is a mid-session fork and is diagnosis (`evidence_role` `diagnosis`). A `step0` trial is `final`. Rules, skills, custom droids, and settings load at session start, so a `final` result for those changes comes from a `step0` job with the change installed. Hooks and tools may be diagnosed from just before the first relevant action when the earlier steps would be identical. Held-out and regression results are `final` and start fresh with the frozen change installed.

A `candidate` arm copies `analysis/proposals/<id>/.factory/` and, when present, `AGENTS.md` onto the task checkout before the session starts. It leaves `proposal.json` and user-global settings alone. Read the checkout path from `retrace.local.json`.

`droid exec --session-id` continues a session in place. `droid exec --fork` copies the whole session. Neither takes a message id. A `checkpoint` job uses the SDK calls above. A `step0` job uses `droid exec`.

Score with the SWE-bench grader. `passed` is that grader's result. An official SWE-bench recipe for `droid exec` is unverified. Run headless `droid exec` in a glibc Docker image and grade with the SWE-bench runner. Write `runs/results/<job-id>/<task-id>-<checkpoint>-<arm>-<trial>.json`, where `<checkpoint>` is the `tool_call_id` or `step0`. Build `model_patch` with `git add -A` and `git diff --cached <base_commit>`, so new files reach the grader.

Held-out and regression runs are `step0` jobs on this same runner, and run only after `splits/` is committed and the candidate directory is frozen.

## Claude Code adapter

Optional, and cut after the extra example cases. The same loop uses the Claude Agent SDK `resumeSessionAt` and `forkSession`. The Python SDK cannot resume from a specific message. If that fork fails, restore the snapshot and start a fresh session seeded with the transcript prefix.
