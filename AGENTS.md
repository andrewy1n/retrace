# Retrace

Harness improvement through replay. Trace features route work. The improvement loop uses only signals a production system has. The dataset's grader is for our own verification (see Grader). Step-0 replay results are the evidence. Report an intervention under a stated setup, with counts, sample size, and an interval. A small or negative result is reported as such.

Droid is the primary harness. Claude Code is an optional adapter. `splits/pool.json` holds the task pool.

## Owners

- Andrew: `recorder/capture`, `recorder/replay`, and `dashboard/`. Writes traces, primitives, and replay results. Runs a job he is given. Owns the Droid SDK rewind and fork, the PostToolUse snapshot hook, `droid exec` runs, primitive extraction from the session JSONL and its Tiger table, Factory credit accounting, held-out and regression runs from step 0, and the dashboard page.
- Kate: `analysis/labeler` and `analysis/proposals`. Writes features, diagnoses, labels, friction tickets, replay jobs, and candidate directories. Reads primitives, traces, and results, except grader output (see Grader). Owns feature discovery, diagnosis, the leak check, change generation, and the Tiger schema except the primitives table.
- `dashboard/` is an Evidence project with a light theme only (`dashboard/README.md` has the run steps). It is the product view, so it shows no grader data. It reads Tiger summaries through `TIGER_DASHBOARD_URL`, local traces, and `runs/reviews/`. It writes nothing. The pull request is the review surface.

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

`contracts/` is the live shape. Edit a schema and its fixture in the same change. There is no version field and no numbered schema directory. A `checkpoint` job names `tool_call_id`s. A `step0` job names instance ids of its dataset. `passed` is the dataset's grader (`recorder/worker/scripts/grade.sh`). The Grader section limits who reads it.

- Trace. One session in `runs/traces/<session-id>.json`. Each step has `tool_call_id`, `message_id` (the Droid `messageId` that `session.rewind` takes), `tool_name`, and `snapshot_ref`. The step does not include tool input or output. The conversation stays in the Droid session. The session also has `harness_session_id` (the id `resumeSession` accepts) and `task_id`. The demo harness value is `droid`.
- Friction ticket. `runs/tickets/<ticket-id>.json`. Fields are `ticket_id`, `friction_type`, `severity`, and `session_ids`. The shape matches a Signals ticket so a later Signals or Linear ticket can seed the same file. The stand-in detector is labeled Signals-style and credits Factory Signals for the ideas it borrows.
- Primitives. One session in `runs/primitives/<session-id>.json`, written by `recorder/capture/primitives.py` from the Droid transcript and `settings.json`. Session fields are `session_id`, `task_id`, `job_id`, `trial`, `harness`, `assistant_turns`, `tool_calls`, `token_usage` (the `tokenUsage` totals, with `factory_credits`), `timed_out`, and `calls`. Each call has `tool_call_id` (matches the trace), `position`, `turn`, `tool_name`, `command_class`, `test_runner`, `path_arg_count` (0 is a whole-suite run), `background`, `duration_s`, `is_error`, `exit_code`, `files`, `output_chars`, `output_tokens_est`, `turns_after`, and `repeats_earlier`. A call has no command text and no tool output. Only classes, counts, and repo paths.
- Replay job. `runs/jobs/<job-id>.json`. `start` is `checkpoint` or `step0`. A `checkpoint` job has `session_id` and `tool_call_ids`. A `step0` job has `task_ids` and runs each task fresh. A job may have `dataset`: `swebench_verified` (default) or `swebench_pro`. A `checkpoint` job with a `control` or `candidate` arm has `continuation`, the message that continues each fork. Every job has an arm (`control`, hint text, or a proposal path), `model`, reruns, stop mode (`next_user_turn`, `reuse_reply`, `simulated_user`), and a Factory credit budget (`budget_credits`).
- Replay result. One trial at `runs/results/<job-id>/<task-id>-<checkpoint>-<arm>-<trial>.json`, where `<checkpoint>` is the `tool_call_id` or `step0`. Fields are `job_id`, `task_id`, `session_id` of the trial's trace when one was recorded, the arm kind, `model`, `droid_version`, the stop mode used, `trial`, `evidence_role`, `cost_credits` from `tokenUsage.factoryCredits`, `proxies`, and `repo_sha` (the HEAD of the checkout that ran `remote.sh submit`, which refuses uncommitted changes in `contracts/` or the candidate directory). A `checkpoint` trial is `diagnosis`, has `tool_call_id`, has no `passed` or `grader`, and is not final evidence. A `step0` trial is `final`, has `passed` and `grader` (`swebench` or `swebench_pro`), and has no `tool_call_id`. `proxies` has `repo_tests` (the repo's own tests at the start commit, chosen from the edited files, run at the start commit and with the patch) and `acceptance` (the task's acceptance check, with its result at the start commit).
- Acceptance check. `runs/acceptance/<task-id>/check.json`, with each file's content under `runs/acceptance/<task-id>/files/<path>`. Fields are `task_id`, `dataset`, `author`, `inputs` (only `instruction` and `start_repo`), `files`, `command` (exit 0 is pass), and `frozen_at`. It is written from the task statement and the start repo only, and frozen before any replay of the task.
- Proposed change. `analysis/proposals/<id>/proposal.json`. Fields are `proposal_id`, the target as exactly one of `failure_type` or `cost_pattern` (a feature name from `analysis/AGENTS.md`), `change_type`, `path`, and optional `pr_url` (the pull request that ships it, set once it exists). The runner copies `.factory/` and `AGENTS.md` from that directory onto the task checkout and leaves `proposal.json` in this repo.

Features, diagnoses, and labels belong to Kate. Andrew does not read them. He gets them only as replay jobs. The label shape is in `analysis/AGENTS.md`.

## Harness under test

The harness is the Droid CLI, the model, and the config Droid loads. It has no checkout of its own. Every result records `droid_version` and `model`.

- Droid. Version 0.249.0, from the host binary mounted into the task container. A `step0` trial runs `droid exec --skip-permissions-unsafe -o json --model <model> --cwd <repo>`. A `checkpoint` trial resumes the recorded session through `@factory/droid-sdk`, rewinds, and streams one turn at autonomy `high`.
- Config in the baseline. The only config is the user-level `~/.factory/hooks.json` that the runner writes into each container. It holds the capture hook. The task repo has no `.factory/` and no `AGENTS.md`.
- A change is an overlay. `analysis/proposals/<id>/.factory/` and `AGENTS.md` are copied into the task checkout (`/app` or `/testbed`) before the session starts. The runner adds both paths to `.git/info/exclude`, so they stay out of the graded patch.
- Shipping a change is a pull request in this repository. It adds `analysis/proposals/<id>/` and the evidence file `reports/<group>.md`. A reader who adopts the change copies the overlay into their own repository.

## Grader

The dataset's grader is the oracle. It is for our own verification only: it shows the impact of a frozen change. The improvement loop runs on signals a production system has, such as traces, primitives, snapshots, the repo's own tests at the start commit, and checks an agent writes from the task statement alone. In production, monitoring and rollback replace the grader.

- Grader output never reaches the loop. Labels, target choice, checkpoint diagnosis, hints, and proposal selection do not read `passed`, the gold patch, the test patch, or the dataset's test lists. This holds for people as well as agents.
- The grader scores step-0 held-out and regression trials after the candidate is frozen. People read those results in `reports/` and in the slides. The dashboard never shows them.
- One frozen run per split. A candidate revised after its held-out or regression results needs new held-out and regression tasks. Otherwise label the result as derived from those tasks.
- Regression tasks stay out of derivation, like held-out tasks.
- Freeze proxy definitions before the derivation run. Report their agreement with the grader as a number, and do not tune a proxy against it.

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
- `runs/acceptance/<task-id>/`
- The GitHub repository is public from the first push. Files in `runs/traces`, `runs/primitives`, `runs/jobs`, `runs/results`, `runs/labels`, `runs/tickets`, `runs/reviews`, and `runs/acceptance` are world-readable.
- `runs/private/` is gitignored. Private sessions stay there and are not committed.
- `splits/` holds derivation, held-out, and regression instance ids.
- `reports/` holds a frozen comparison, including its count, interval, and Factory credits. `recorder/replay/report.py` writes it from `runs/results/` (arms, Wilson and paired bootstrap intervals, McNemar test, credits). `reports/preregistration.md` is committed before the first derivation run.
- Tiger Data backs the dashboard with session metadata, primitives, features, labels, abstracted citations, replay outcomes, and shipped-change summaries. Raw transcripts and repo contents stay on the machine unless the user opts in.

A proposal directory is an overlay the runner copies onto the task checkout:

```
analysis/proposals/<id>/.factory/
analysis/proposals/<id>/AGENTS.md
```

`.factory/` holds `hooks.json`, `hooks/`, `skills/`, `droids/`, and settings. The job's candidate path is portable, such as `analysis/proposals/block-test-edits`. The runner reads the directory from the worker's repo checkout at `/opt/retrace/repo/<path>`. `recorder/worker/remote.sh submit` copies it there.

The dashboard home page lists proposals, with those waiting for review first. Each card shows the change in the targeted behaviour's incidence with its interval, the credit difference, the proxy guard (repo-test regressions and the acceptance check), and a link to the pull request (`pr_url`). A proposal page has Overview (the overlay and its diff, and rollback), Evidence, and Replay tabs. Runs and Sessions show credits, turns, test behaviour from primitives, and proxies. Monitoring shows the targeted behaviour, credits, and proxies after a change ships, with rollback. Those numbers are Tiger summaries. Until Kate's proposals exist, `dashboard/sources/mock/proposals.csv` holds labeled example rows.

Snapshot commits stay in the task repo, pinned under `refs/retrace/`. The trace stores the commit id. Tool input and output stay in the Droid session.

## Environment

Values stay out of git. These facts were checked on 2026-10-24.

- `.env` at the repo root is gitignored and holds `FACTORY_API_KEY`, `VULTR_API_KEY`, `TIGER_DATABASE_URL` (role `retrace_worker`: select, insert, update), `TIGER_DASHBOARD_URL` (role `retrace_dashboard`: reads `primitives_sessions`, `primitives_calls`, and the view `replay_runs`, which has no `passed` or `grader`; it cannot read `replay_results`), and `TIGER_ANALYSIS_URL` (role `retrace_analysis`: reads the public tables, owns the schema `analysis`, and `retrace_dashboard` reads new tables there). `TIGER_ANALYSIS_URL` is for Kate. Load it with `set -a; . ./.env; set +a`. Never print or commit a value. The Tiger service is `retrace` (`jqa8vnnbh6`). The `tiger` CLI is installed and logged in, and `tiger db query <service> -c '<sql>'` runs SQL as the owner (add `--read-only` for a read). The tables match `contracts/tiger-*.sql` (applied 2026-10-24). `tiger_sink.py` needs `psycopg`, which system Python lacks, so use a venv made with `--system-site-packages`. Send a connection string to Kate privately.
- The Vultr API key accepts calls only from the IP addresses on its allowlist (Vultr console, Account, API, Access Control). From another address the API returns `Unauthorized IP address`. A new network means a new address. `vultr-cli` is not installed on the dev machine.
- Keep the worker address in gitignored `retrace.local.json` as `vm_host`. Reach it with `ssh root@<vm_host>` and `~/.ssh/id_ed25519`. SSH does not depend on the API allowlist. `~/.ssh/known_hosts` is hashed, so it does not show the address. On the worker, `/root/.retrace.env` (mode 600) exports `FACTORY_API_KEY` and `TIGER_DATABASE_URL`, so `grade.sh` writes each graded result to Tiger. Source it before `run_job.sh`, and run long jobs in `tmux`. The worker's `/opt/retrace/*.sh` and `retrace_job.py` are copies of `recorder/worker/scripts/`, so reinstall them after a change with `recorder/worker/remote.sh install` when no job runs. `remote.sh submit <job.json>` runs and grades a job on the worker and copies the results back.
- The dev machine is arm64 (WSL2). The SWE-bench images are amd64 only, so run trials, checkpoint forks, and grading on the x86 worker. `RETRACE_IMAGE`, `RETRACE_PLATFORM`, and `RETRACE_DROID` let `recorder/replay/run_checkpoint.sh` use an Epoch arm64 image for a local check only. Its results are not evidence. The dev machine has Docker, the Droid CLI at `~/.local/bin/droid`, node 24, `gh`, `jq`, and Python with `jsonschema` and `numpy`. It has no `psql`.
- `recorder/worker/scripts/retrace_job.py` reads schemas from `/opt/retrace/repo`. On the dev machine, run it with `RETRACE_REPO=$PWD RETRACE_ROOT=$PWD`.
- Copies of worker trials are in `runs/private/sessions/<session-id>/`: `factory-sessions/-testbed/<droid-id>.jsonl` (the transcript), `<droid-id>.settings.json` (session token totals by type), `meta.json`, `droid.json`, `capture/`, `snapshots.bundle`, and `start_commit`. The transcript has a timestamp on every line and `is_error` on every tool result. It has no per-turn token counts. On Pro, `start_commit` equals the dataset `base_commit`, so `snapshots.bundle` needs that commit's parents, two of them when it is a merge. The bundle header lists them on lines that start with `-`. `analysis/labeler/session.py` fetches each one from GitHub by id.
- Factory credits per token, from an exact fit over 80 baseline1 sessions on `claude-haiku-5-5`: 0.2 per output token (thinking included), 0.05 per cache-write token, 0.004 per cache-read token, and about 0.26 per uncached input token.
- The benchmark is moving to SWE-bench Pro V2 (`ScaleAI/SWE-bench_Pro`, config `default`, 642 tasks, 11 repos). Retrace uses the Python and Go repos: ansible, openlibrary, qutebrowser, flipt, teleport, vuls, navidrome. The dataset has no eval script. Scale's `scaleapi/SWE-bench_Pro-os` ships Harbor tasks under `v2/tasks/<instance_id>/` (`instruction.md`, `tests/test.sh`, `task.toml`). Retrace pins commit `66f92766bba642462d4bbe5479e83f91f9211862`, cloned to `/opt/retrace/swe-bench-pro` on the worker. The prompt is `instruction.md`. The repo is at `/app`. The image is `ghcr.io/scaleapi/swe-bench_pro-v2:<instance_id>`. Grading runs `bash /tests/test.sh` in a fresh container with the patch applied, and reads `reward.txt`. V2 does not use `before_repo_set_cmd`. Droid needs the Factory API, so the agent has network access, and the official no-network protocol does not hold. Details and measurements are in `recorder/worker/README.md`. Gold passes and empty fails on all 56 tasks of `splits/pro-candidates.json` (`splits/pro-gold-check.json`). Those images take 275 GB, 2.1 to 11.9 GB each. A pull takes 30 to 130 s.
- Pro cost, measured on `pro-baseline1` (50 of 64 trials, `claude-haiku-5-5`, control arm, all 50 pass): 14,025 credits per trial on average, 10,606 median, 70,057 maximum. Mean per repo: ansible 15,188, openlibrary 15,600, flipt 7,435, teleport 22,398 (5 trials). Verified means are 4,436 (baseline1) and 6,309 (baseline2). A Pro session takes 17 to 34 assistant turns on average per repo, against 13 and 16 on Verified.
- Fork cost, measured on 12 checkpoint forks of one ansible session (steps 10 and 17 of 43, `claude-haiku-5-5`): 16,426 credits per fork on average, 4,838 minimum, 25,074 maximum. A fork from an early step re-runs most of the task, so it costs about as much as a full Pro trial. A fork from a late step costs less.
- `run_job.sh` sums `cost_credits` over every finished trial in the job directory and checks that sum only when a trial starts. Trials in flight are not counted. `pro-baseline1` spent 701,253 against a cap of 500,000. Set `budget_credits` above the credits already spent when you re-run a job.
- `proxies.sh` ran on the worker on 2026-10-24 on four `pro-baseline1` trials, one each from ansible, openlibrary, flipt, and teleport. `repo_tests` selected 1 to 3 test files or packages per trial, found 5 to 113 tests passing at the start commit and 0 regressed, and took 5 to 110 s per trial for both runs. A Python image has `python` on PATH, and a Go image has `go`. The acceptance check gave `fail` at the start commit and `fail` with the patch on one ansible trial, with a throwaway check. On 2026-10-25 a throwaway check gave `fail` at the start commit and `pass` with the patch on an openlibrary trial.
- `pro-runcheck1-control` and `pro-runcheck1-candidate` (2026-10-25) ran the step-0 path on two Pro dev tasks, one trial each. The candidate is the no-op overlay `recorder/worker/test-overlay`. Its hook fired on every tool call, and no patch contains `.factory/` or `AGENTS.md`. Every result has `proxies` and `repo_sha`. `repo_tests` finds no test for a package whose only test file the patch adds, as on the flipt task. These are runner checks, not evidence.
- Teleport images whose id ends in `-vee9b09fb20c43af7e520f57e9239bbcf46b7113d` are Alpine (musl). The glibc Droid binary fails there with `Error relocating /usr/local/bin/droid: __pthread_key_create: symbol not found`, and the trial writes no result. Three dev tasks of `splits/pro-pool.json` have this suffix. No held-out task has it. One image was checked directly (`teleport-32bcd715`), and the other two failed with the same error.
- SWE-bench Verified has 500 tasks. The 1 to 4 hour band has 42, and 22 of them are django. `splits/draw_pool.py` and `analysis/labeler/fetch_tasks.py` read it from the Hugging Face datasets-server API.
- One `read_doc` result for the project doc is about 540 KB, so the Google Docs connector saves it to a file. Use the Google Workspace skill's `docs_index.py` for positions, and send each edit with the latest `revisionId`. The doc has two tabs: the main tab `t.0` and Architecture `t.kt15rr8inhru`.

## Unverified

These items change code. The rest are in the Unverified section of the project doc.

- `proxies.sh` on a Verified image. Only a fake `docker` covered it.
- A fresh session seeded from the Droid transcript when rewind fails. Not implemented. Rewind worked on Droid 0.249.0 with `@factory/droid-sdk` 0.10.0 on 2026-10-24 (see `recorder/AGENTS.md`).
- A checkpoint fork graded by the SWE-bench grader on a Verified image. A Pro fork ran and passed the Pro verifier on the x86 worker on 2026-10-24 (`runs/results/pro-fork1/`). The Verified fork ran only on an arm64 test image.
- Whether Pro results from this runner compare to the Scale leaderboard. The agent phase has network access, containers have no CPU or memory cap, and the Droid CLI is not a Scale-reviewed agent.
- Whether any of the 642 Pro tasks keeps its repo in `/testbed`. The runner handles it, but all 56 images checked use `/app`.
- Whether a candidate overlay's `AGENTS.md` reaches a resumed session. Its hooks do.
- The session JSONL layout at `~/.factory/sessions/<cwd-slug>/<id>.jsonl`. It comes from third-party parsers.
- Whether the snapshot hook causes Droid's "modified externally since it was last read" Edit errors. In baseline1, 9 of 12 follow a shell write by the agent to that file. 3 follow only test runs, in `django-13279` trial 3 and `sympy-23413` trial 1. `snapshot.sh` writes only a temporary index.
- Droid in an Alpine (musl) Pro image. Not implemented. The three affected dev tasks are dropped from the pool (see the Decided section of the project doc).
- An official SWE-bench recipe for `droid exec`. The runner is our own glibc Docker image, graded with the SWE-bench runner.
