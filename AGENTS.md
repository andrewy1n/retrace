# Retrace

Harness improvement through replay. Trace features route work. Step-0 replay results are the evidence. Report an intervention under a stated setup, with counts, sample size, and an interval. A small or negative result is reported as such.

Droid is the primary harness. Claude Code is an optional adapter. The hackathon pool is 20 to 40 tasks.

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

Do not add a `CLAUDE.md`. Claude Code reads this file when no `CLAUDE.md` is present. A proposal ships an `AGENTS.md` rule only as the last-ranked change.

## Contract

`contracts/` is the live shape. Edit a schema and its fixture in the same change. There is no version field and no numbered schema directory. A `checkpoint` job names `tool_call_id`s. A `step0` job names SWE-bench instance ids. Pass/fail is the SWE-bench grader in `recorder/replay`.

- Trace. One session in `runs/traces/<session-id>.json`. Each step has `tool_call_id`, `message_id` (the Droid `messageId` that `session.rewind` takes), `tool_name`, and `snapshot_ref`. The step does not include tool input or output. The conversation stays in the Droid session. The session also has `harness_session_id` (the id `resumeSession` accepts) and `task_id`. The demo harness value is `droid`.
- Friction ticket. `runs/tickets/<ticket-id>.json`. Fields are `ticket_id`, `friction_type`, `severity`, and `session_ids`. The shape matches a Signals ticket so a later Signals or Linear ticket can seed the same file. The stand-in detector is labeled Signals-style and credits Factory Signals for the ideas it borrows.
- Replay job. `runs/jobs/<job-id>.json`. `start` is `checkpoint` or `step0`. A `checkpoint` job has `session_id` and `tool_call_ids`. A `step0` job has `task_ids` and runs each task fresh. Every job has an arm (`control`, hint text, or a proposal path), `model`, reruns, stop mode (`next_user_turn`, `reuse_reply`, `simulated_user`), and a Factory credit budget (`budget_credits`).
- Replay result. One trial at `runs/results/<job-id>/<task-id>-<checkpoint>-<arm>-<trial>.json`, where `<checkpoint>` is the `tool_call_id` or `step0`. Fields are `job_id`, `task_id`, `session_id` of the trial's trace when one was recorded, the arm kind, `model`, `droid_version`, the stop mode used, `trial`, `passed`, `grader`, `evidence_role`, and `cost_credits` from `tokenUsage.factoryCredits`. A `checkpoint` trial is `diagnosis`, has `tool_call_id`, and is not final evidence. A `step0` trial is `final` and has no `tool_call_id`.
- Proposed change. `analysis/proposals/<id>/proposal.json`. Fields are `proposal_id`, `failure_type`, `change_type`, and `path`. The runner copies `.factory/` and `AGENTS.md` from that directory onto the task checkout and leaves `proposal.json` in this repo.

Features, diagnoses, and labels belong to Kate. Andrew does not read them. He gets them only as replay jobs. The label shape is in `analysis/AGENTS.md`.

## Gates

1. A schema change. The other person pulls that SHA.
2. The first real trace.
3. The chosen target (a failure group or a cost pattern), with `splits/` committed before anyone studies the held-out tasks. The hackathon pool is 20 to 40 tasks.
4. The candidate directory frozen before held-out and regression runs. Those runs start fresh from step 0.

If the biggest failure group is too small to split, widen the task pool before writing jobs. A group that stays at 3 to 5 sessions is labeled small and uses monitoring plus rollback.

`session.rewind` restores only the file snapshots passed to it, from `getRewindInfo`. It does not restore the whole repo. Git snapshots stay the source of truth. The runner restores `snapshot_ref` with `recorder/replay/restore.sh` after rewind. Checked against `@factory/droid-sdk` 0.10.0 and the TypeScript SDK docs on 2026-10-22. If rewind fails, restore the snapshot and start a fresh session seeded with the transcript prefix. That fallback is unverified.

## Layout

- `runs/labels/<session-id>.json`
- `runs/tickets/<ticket-id>.json`
- `runs/reviews/<proposal-id>.json`
- The GitHub repository is public from the first push. Files in `runs/traces`, `runs/jobs`, `runs/results`, `runs/labels`, `runs/tickets`, and `runs/reviews` are world-readable.
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

## Unverified

These items change code. The rest are in the Unverified section of the project doc.

- Whether the installed Droid CLI's rewind matches `@factory/droid-sdk` 0.10.0. The published SDK restores only the passed file snapshots. A live run is not required for that conclusion.
- Whether a resumed session can leave its saved working directory. Until then, trials on that checkout run one at a time.
- A fresh session seeded from the Droid transcript when rewind fails.
- The session JSONL layout at `~/.factory/sessions/<cwd-slug>/<id>.jsonl`. It comes from third-party parsers.
- An official SWE-bench recipe for `droid exec`. The runner is our own glibc Docker image, graded with the SWE-bench runner.
