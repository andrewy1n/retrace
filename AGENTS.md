# Retrace

Harness improvement through replay. Trace features route work. Step-0 replay results are the evidence. Report an intervention under a stated setup, with counts, sample size, and an interval. A small or negative result is reported as such.

Droid is the primary harness. Claude Code is an optional adapter. `splits/pool.json` holds the task pool.

## Owners

- Andrew: `recorder/capture`, `recorder/replay`, and `dashboard/`. Writes traces, primitives, and replay results. Runs a job he is given. Owns the Droid SDK rewind and fork, the PostToolUse snapshot hook, `droid exec` runs, primitive extraction from the session JSONL and its Tiger table, Factory credit accounting, held-out and regression runs from step 0, and the dashboard page.
- Kate: `analysis/labeler` and `analysis/proposals`. Writes features, diagnoses, labels, friction tickets, replay jobs, and candidate directories. Reads primitives, traces, and results. Owns feature discovery, diagnosis, the leak check, change generation, and the Tiger schema except the primitives table.
- `dashboard/` is created with its first page. It reads Tiger summaries and local traces. It writes only `runs/reviews/`.

`recorder/capture`, `recorder/replay`, `analysis/labeler`, `analysis/proposals`, and `dashboard/` appear with their first source file.

## Project doc

https://docs.google.com/document/d/1sAXpAyjByro-vfbUc1EXLp-weLUiXahmg3GEDRCgrrw/edit

People and agents read and write the project doc.

The doc has one heading per section: Pitch, Now, Open, Decided, Contract, and Unverified. Pitch replaces `retrace-summary-v2.pdf`, which is superseded. Now holds the order, owners, and the cut list. Decided is append-only. Unverified holds items that do not change code. An Architecture tab describes the pipeline stages, their owners, and the evidence rules. This file does not copy the plan.

Git holds what code depends on: schemas, splits, the pre-registration, rules in `AGENTS.md`, and results. The doc holds the plan and the pitch. When the two disagree, git wins for code, and the doc wins for the plan.

For agents:

- Read the doc for a plan fact such as the target behaviour, the model, the pool, or a split. If neither git nor the doc states it, ask the person. Do not guess.
- At the end of a task that changes a contract, merges a decision, or resolves an unverified item, add one line to the right section, for example: "Contract: <sha>, replay job gains `start`." Change only the rows the task touches. In Decided, add a row and never edit an old one.
- Without a Google Docs connector, give the person that line instead, and do not claim the doc is updated.
- A contract change stays under Open until it is merged. Then Contract stores the SHA and one line.
- The doc may hold session ids, failure-type counts, instance ids in flight, and the SHA to pull. Schemas, transcripts, repository contents, and result tables stay in git.
- When you find or rederive a fact that work depends on, such as an access path, a file layout, a tool on the machine, or a measured number, and this file lacks it or states it wrongly, fix this file in the same change. Keep secret values and addresses out of it.

Do not add a `CLAUDE.md`. Claude Code reads this file when no `CLAUDE.md` is present. A proposal ships an `AGENTS.md` rule only as the last-ranked change.

## Contract

`contracts/` is the live shape. Edit a schema and its fixture in the same change. There is no version field and no numbered schema directory. A `checkpoint` job names `tool_call_id`s. A `step0` job names SWE-bench instance ids. Pass/fail is the SWE-bench grader in `recorder/replay`.

- Trace. One session in `runs/traces/<session-id>.json`. Each step has `tool_call_id`, `message_id` (the Droid `messageId` that `session.rewind` takes), `tool_name`, and `snapshot_ref`. The step does not include tool input or output. The conversation stays in the Droid session. The session also has `harness_session_id` (the id `resumeSession` accepts) and `task_id`. The demo harness value is `droid`.
- Friction ticket. `runs/tickets/<ticket-id>.json`. Fields are `ticket_id`, `friction_type`, `severity`, and `session_ids`. The shape matches a Signals ticket so a later Signals or Linear ticket can seed the same file. The stand-in detector is labeled Signals-style and credits Factory Signals for the ideas it borrows.
- Primitives. One session in `runs/primitives/<session-id>.json`, written by `recorder/capture/primitives.py` from the Droid transcript and `settings.json`. Session fields are `session_id`, `task_id`, `job_id`, `trial`, `harness`, `assistant_turns`, `tool_calls`, `token_usage` (the `tokenUsage` totals, with `factory_credits`), `timed_out`, and `calls`. Each call has `tool_call_id` (matches the trace), `position`, `turn`, `tool_name`, `command_class`, `test_runner`, `path_arg_count` (0 is a whole-suite run), `background`, `duration_s`, `is_error`, `exit_code`, `files`, `output_chars`, `output_tokens_est`, `turns_after`, and `repeats_earlier`. A call has no command text and no tool output. Only classes, counts, and repo paths.
- Replay job. `runs/jobs/<job-id>.json`. `start` is `checkpoint` or `step0`. A `checkpoint` job has `session_id` and `tool_call_ids`. A `step0` job has `task_ids` and runs each task fresh. Every job has an arm (`control`, hint text, or a proposal path), `model`, reruns, stop mode (`next_user_turn`, `reuse_reply`, `simulated_user`), and a Factory credit budget (`budget_credits`).
- Replay result. One trial at `runs/results/<job-id>/<task-id>-<checkpoint>-<arm>-<trial>.json`, where `<checkpoint>` is the `tool_call_id` or `step0`. Fields are `job_id`, `task_id`, `session_id` of the trial's trace when one was recorded, the arm kind, `model`, `droid_version`, the stop mode used, `trial`, `passed`, `grader`, `evidence_role`, and `cost_credits` from `tokenUsage.factoryCredits`. A `checkpoint` trial is `diagnosis`, has `tool_call_id`, and is not final evidence. A `step0` trial is `final` and has no `tool_call_id`.
- Proposed change. `analysis/proposals/<id>/proposal.json`. Fields are `proposal_id`, `failure_type`, `change_type`, and `path`. The runner copies `.factory/` and `AGENTS.md` from that directory onto the task checkout and leaves `proposal.json` in this repo.

Features, diagnoses, and labels belong to Kate. Andrew does not read them. He gets them only as replay jobs. The label shape is in `analysis/AGENTS.md`.

## Gates

1. A schema change. The other person pulls that SHA.
2. The first real trace.
3. The chosen target (a failure group or a cost pattern), with `splits/` committed before anyone studies the held-out tasks.
4. The candidate directory frozen before held-out and regression runs. Those runs start fresh from step 0.

If the biggest failure group is too small to split, widen the task pool before writing jobs. A group that stays at 3 to 5 sessions is labeled small and uses monitoring plus rollback.

`session.rewind` restores only the file snapshots passed to it, from `getRewindInfo`. It does not restore the whole repo. Git snapshots stay the source of truth. The runner restores `snapshot_ref` with `recorder/replay/restore.sh` after rewind. Checked against `@factory/droid-sdk` 0.10.0 and the TypeScript SDK docs on 2026-10-22. If rewind fails, restore the snapshot and start a fresh session seeded with the transcript prefix. That fallback is unverified.

## Layout

- `runs/primitives/<session-id>.json`
- `runs/labels/<session-id>.json`
- `runs/tickets/<ticket-id>.json`
- `runs/reviews/<proposal-id>.json`
- The GitHub repository is public from the first push. Files in `runs/traces`, `runs/primitives`, `runs/jobs`, `runs/results`, `runs/labels`, `runs/tickets`, and `runs/reviews` are world-readable.
- `runs/private/` is gitignored. Private sessions stay there and are not committed.
- `splits/` holds derivation, held-out, and regression instance ids.
- `reports/` holds a frozen comparison, including its count, interval, and Factory credits. `reports/preregistration.md` is committed before the first derivation run.
- Tiger Data backs the dashboard with session metadata, primitives, features, labels, abstracted citations, replay outcomes, and shipped-change summaries. Raw transcripts and repo contents stay on the machine unless the user opts in.

A proposal directory is an overlay the runner copies onto the task checkout:

```
analysis/proposals/<id>/.factory/
analysis/proposals/<id>/AGENTS.md
```

`.factory/` holds `hooks.json`, `hooks/`, `skills/`, `droids/`, and settings. The job's candidate path is portable, such as `analysis/proposals/block-test-edits`. The machine-local harness checkout path lives in gitignored `retrace.local.json`.

The proposal screen starts from the friction ticket and shows the `.factory/hooks.json` guardrail. The Changes tab shows a before-and-after of the target failure type against untargeted types, a shipped-changes table, and rollback. Those numbers are Tiger summaries. Mockup figures are examples.

Snapshot commits stay in the task repo, pinned under `refs/retrace/`. The trace stores the commit id. Tool input and output stay in the Droid session.

## Environment

Values stay out of git. These facts were checked on 2026-10-24.

- `.env` at the repo root is gitignored and holds `FACTORY_API_KEY` and `VULTR_API_KEY`. Load it with `set -a; . ./.env; set +a`. Never print or commit a value. The Tiger connection string is not on the dev machine. When it is added, name it `TIGER_DATABASE_URL`.
- The Vultr API key accepts calls only from the IP addresses on its allowlist (Vultr console, Account, API, Access Control). From another address the API returns `Unauthorized IP address`. A new network means a new address. `vultr-cli` is not installed on the dev machine.
- Keep the worker address in gitignored `retrace.local.json` as `vm_host`. Reach it with `ssh root@<vm_host>` and `~/.ssh/id_ed25519`. SSH does not depend on the API allowlist. `~/.ssh/known_hosts` is hashed, so it does not show the address. On the worker, `/root/.retrace.env` (mode 600) exports `FACTORY_API_KEY`. Source it before `run_job.sh`, and run long jobs in `tmux`. The worker's `/opt/retrace/*.sh` and `retrace_job.py` are copies of `recorder/worker/scripts/`, so reinstall them after a change.
- The dev machine is arm64 (WSL2). The SWE-bench images are amd64 only, so run trials and grading on the x86 worker. The dev machine has Docker, the Droid CLI at `~/.local/bin/droid`, node 24, `gh`, `jq`, and Python with `jsonschema` and `numpy`. It has no `psql`.
- `recorder/worker/scripts/retrace_job.py` reads schemas from `/opt/retrace/repo`. On the dev machine, run it with `RETRACE_REPO=$PWD RETRACE_ROOT=$PWD`.
- Copies of worker trials are in `runs/private/sessions/<session-id>/`: `factory-sessions/-testbed/<droid-id>.jsonl` (the transcript), `<droid-id>.settings.json` (session token totals by type), `meta.json`, `droid.json`, `capture/`, `snapshots.bundle`, and `start_commit`. The transcript has a timestamp on every line and `is_error` on every tool result. It has no per-turn token counts.
- Factory credits per token, from an exact fit over 80 baseline1 sessions on `claude-haiku-5-5`: 0.2 per output token (thinking included), 0.05 per cache-write token, 0.004 per cache-read token, and about 0.26 per uncached input token.
- SWE-bench Verified has 500 tasks. The 1 to 4 hour band has 42, and 22 of them are django. `splits/draw_pool.py` and `analysis/labeler/fetch_tasks.py` read it from the Hugging Face datasets-server API.
- One `read_doc` result for the project doc is about 540 KB, so the Google Docs connector saves it to a file. Use the Google Workspace skill's `docs_index.py` for positions, and send each edit with the latest `revisionId`. The doc has two tabs: the main tab `t.0` and Architecture `t.kt15rr8inhru`.

## Unverified

These items change code. The rest are in the Unverified section of the project doc.

- Whether the installed Droid CLI's rewind matches `@factory/droid-sdk` 0.10.0. The published SDK restores only the passed file snapshots. A live run is not required for that conclusion.
- Whether a resumed session can leave its saved working directory. Until then, trials on that checkout run one at a time.
- A fresh session seeded from the Droid transcript when rewind fails.
- The session JSONL layout at `~/.factory/sessions/<cwd-slug>/<id>.jsonl`. It comes from third-party parsers.
- An official SWE-bench recipe for `droid exec`. The runner is our own glibc Docker image, graded with the SWE-bench runner.
