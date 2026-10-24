# Recorder and replay

Andrew owns this tree and the dashboard. Kate owns labels, jobs, proposals, and the Tiger schema.

`capture/` is the Droid PostToolUse hook. `replay/` is the runner. Create each directory with its first source file. Claude Code is an optional adapter. Cut the extra example cases first, then this adapter.

## Capture

After every tool call, a PostToolUse hook runs `capture/hook.py`, which calls `capture/snapshot.sh` and logs the printed commit id as `snapshot_ref`. Install the hook in the user-level `~/.factory/hooks.json`, not the project one, so a candidate's `.factory/hooks.json` cannot replace it. Both levels run: on 2026-10-24 (Droid 0.249.0) a candidate PostToolUse hook and the capture hook each fired on all 4 tool calls of `django-16527`, and the patch left out `.factory/`. The snapshot includes untracked files and omits ignored files. It builds a temporary index from `HEAD` and adds every file, so the working tree, the index, and the branch stay unchanged. Copying the real index can miss a same-size edit made within about a second of its last write, because git trusts the saved timestamps. On a Windows checkout that cost 2 of 10 edits. Rebuilding costs about 0.7 s per snapshot on a django image. It always prints a commit, even on a clean tree. Each commit is pinned under `refs/retrace/` so `git gc` keeps it. Keep the task repo's `.git` and `~/.factory` on volumes that outlive the container. The trace step also stores `tool_call_id`, `message_id`, and `tool_name`. It does not store tool input or output. The conversation stays in the Droid session.

The hook input has `session_id`, `transcript_path`, `cwd`, `tool_name` and `tool_input`, but no `message_id` and no tool-use id (checked on Droid 0.248.0 and 0.249.0). Droid runs no PostToolUse hook for a failed tool call. `capture/trace.py` reads the Droid session JSONL, takes each `tool_use` block's `id` and its assistant message's `id` as `tool_call_id` and `message_id`, and joins the hook log by `tool_name` and `tool_input` in order. A failed call takes the previous step's `snapshot_ref`. Tolerate schema drift. Write `runs/traces/<session-id>.json` so it validates against `contracts/trace.schema.json`. Skip sessions whose outcome depends on state outside the repo. Private sessions go in `runs/private/` and stay uncommitted.

Store `harness_session_id` as the id `resumeSession` accepts. For a SWE-bench task, `task_id` is the instance id. The demo `harness` value is `droid`.

Droid session files are JSONL at `~/.factory/sessions/<cwd-slug>/<id>.jsonl`. The `session_start`, `message` and `tool_use` shapes that `trace.py` reads were checked on Droid 0.248.0 and 0.249.0. Which message id `session.rewind` accepts for a step is unverified.

Several tool calls can share one `message_id`, since Droid puts parallel calls in one assistant message. In the django trace, two reads and one command share a message.

## Finding a trace's snapshots

The worker links `/opt/retrace/sessions/<session_id>` to each trial's output directory. `snapshots.bundle` there holds the image's HEAD commit and every snapshot, and needs only the upstream repo at the dataset `base_commit`. To read a trace, clone the upstream repo (or `git fetch` that commit into an empty one), then run `git fetch <dir>/snapshots.bundle 'refs/retrace/*:refs/retrace/*'`. `<dir>/start_commit` is the diff base. `<dir>/droid.json`, `factory-sessions/` and `capture/` sit next to it. Copy the directory off the VM before the VM is deleted.

In a SWE-bench image, `/testbed` HEAD is a commit on top of the dataset `base_commit` that changes the file mode of every file and no content. Diff a session against the parent of its first snapshot, which is that HEAD. A diff against `base_commit` lists every file as changed.

## Rewind

`session.rewind` restores only the file snapshots passed in `filesToRestore`. Those objects come from `getRewindInfo` and carry `filePath`, `contentHash`, and `size`. `filesToDelete` entries are `{ filePath }`. Evicted files are not restored. The call returns a successor session, and that successor is the fork. `forkTitle` is required. `session.fork()` copies the current conversation and does not rewind.

Checked against `@factory/droid-sdk` 0.10.0 and the TypeScript SDK docs on 2026-10-22. A live rewind is not required to confirm this. Git snapshots stay the source of truth. After rewind, run `replay/restore.sh <snapshot_ref>` on the checkout. It restores the working tree, removes files created later, resets the index and `HEAD` to the snapshot's parent, and keeps ignored files.

If rewind fails, restore the snapshot and start a fresh session seeded with the transcript prefix from the Droid session. That fallback is unverified.

## Replay

A `checkpoint` job resumes the Droid session, rewinds to the step's `message_id`, restores `snapshot_ref`, runs the arm, and writes one result file per trial. A `step0` job starts each task in `task_ids` fresh at its base commit, with the arm installed. Record `model` and `droid --version` on every result. It does not choose checkpoints, write hints, label failures, or turn a hint into a harness change.

Call `resumeSession(harness_session_id)`, then `getRewindInfo({ messageId })`, then `session.rewind({ messageId, filesToRestore, filesToDelete, forkTitle })`. Continue on the successor. `resumeSession` pins the saved working directory, so trials on that checkout run one at a time until a directory change is verified.

Read cost from each turn's `tokenUsage.factoryCredits` and sum those into `cost_credits`. The field is optional and covers one `stream()` call. `TokenUsageUpdate` is the session total and can include the prefix. Cap the job at `budget_credits`. The session JSONL has no per-turn token counts. `<id>.settings.json` next to it holds the session's `tokenUsage` totals by token type, including `factoryCredits`, and it survives a `DROID_TIMEOUT` kill that leaves `droid.json` empty. Cal Hacks has posted no hacker spending allotment. The Factory track prize is $2,000 cash, Factory credits, and swag, with no credit quantity.

Stop modes are `next_user_turn`, `reuse_reply`, and `simulated_user`. Record the mode actually used. The first two carry full evidence weight while the branch still matches. `simulated_user` is weaker and stays labeled as such. The text of the no-hint control is unset.

A `checkpoint` trial is a mid-session fork and is diagnosis (`evidence_role` `diagnosis`). A `step0` trial is `final`. Rules, skills, custom droids, and settings load at session start, so a `final` result for those changes comes from a `step0` job with the change installed. Hooks and tools may be diagnosed from just before the first relevant action when the earlier steps would be identical. Held-out and regression results are `final` and start fresh with the frozen change installed.

A `candidate` arm copies `analysis/proposals/<id>/.factory/` and, when present, `AGENTS.md` onto the task checkout before the session starts. It leaves `proposal.json` and user-global settings alone. Read the checkout path from `retrace.local.json`.

`droid exec --session-id` continues a session in place. `droid exec --fork` copies the whole session. Neither takes a message id. A `checkpoint` job uses the SDK calls above. A `step0` job uses `droid exec`.

Score with the SWE-bench grader. `passed` is that grader's result. An official SWE-bench recipe for `droid exec` is unverified. Run headless `droid exec` in a glibc Docker image and grade with the SWE-bench runner. Write `runs/results/<job-id>/<task-id>-<checkpoint>-<arm>-<trial>.json`, where `<checkpoint>` is the `tool_call_id` or `step0`. Build `model_patch` with `git add -A` and `git diff --cached <HEAD at container start>`, so new files reach the grader. The SWE-bench image's HEAD is a commit on top of `base_commit` that changes file modes, so a diff against `base_commit` lists thousands of files.

Held-out and regression runs are `step0` jobs on this same runner, and run only after `splits/` is committed and the candidate directory is frozen.

## Claude Code adapter

Optional, and cut after the extra example cases. The same loop uses the Claude Agent SDK `resumeSessionAt` and `forkSession`. The Python SDK cannot resume from a specific message. If that fork fails, restore the snapshot and start a fresh session seeded with the transcript prefix.
