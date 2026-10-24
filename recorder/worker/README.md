# Retrace on Vultr: replay/grading worker

One x86_64 VM runs `droid exec` inside the official SWE-bench Verified or SWE-bench Pro images and grades the patches with the matching official harness. Laptops (Windows/WSL, Mac) can't do this well because the images are amd64 only.

Files:
- `cloud-init.yaml`: user data for the VM (generated, do not hand-edit)
- `scripts/prepull.sh`, `run_job.sh`, `run_trial.sh`, `grade.sh`, `grade_pro.sh`, `pro_task.sh`, `retrace_job.py`, `tiger_sink.py`: installed to `/opt/retrace/`
- `../replay/run_checkpoint.sh`, `docker-droid.sh`, `restore.sh`, `fork.mjs`, `package.json`, `package-lock.json`: installed to `/opt/retrace/replay/`. They run `checkpoint` jobs.
- `build_cloud_init.py`: regenerates `cloud-init.yaml` after you edit a script

Target: plan `vc2-16c-64gb` (16 shared vCPU, 64 GB RAM, 1280 GB SSD, $0.438/hr), region `sjc` (Silicon Valley), OS id `2284` = Ubuntu 24.04 LTS x64. All three were checked against `api.vultr.com/v2` on 23 Oct 2026.

## 1. Credits and limits (do first)
1. Get the MLH promo code: register at https://mlh.link/vultr-discover (see https://www.mlh.com/partners/vultr). Company = your school, Job Title = "Student". One registration per person.
2. Create the Vultr account and redeem the code under **Billing → Gift Code**. A card or PayPal must be linked. You'll see a small temporary authorization hold. Promo credits expire.
3. Open **Billing → Limits** (https://console.vultr.com/billing/#billinglimits). Check the max instances and the max instance cost. If a 16 vCPU / $320-per-month plan is over the limit, click **Request Limit Increase** now and describe the use case ("hackathon: SWE-bench evaluation in Docker, 1 to 2 VMs for 2 days"). Approval time is unknown, so ask early. If it blocks you, use the fallback below.
4. Create an API key under **Account → API**. Allow your IP under Access Control.

## 2. Create the VM
Install the CLI with `brew install vultr/vultr-cli/vultr-cli`, a release binary (https://github.com/vultr/vultr-cli/releases), or `go install github.com/vultr/vultr-cli/v3@latest`.

```bash
export VULTR_API_KEY=...            # never commit this
vultr-cli ssh-key create --name retrace --key "$(cat ~/.ssh/id_ed25519.pub)"
vultr-cli ssh-key list              # copy the key ID
vultr-cli instance create \
  --region sjc --plan vc2-16c-64gb --os 2284 \
  --label retrace-worker-1 --host retrace-worker-1 --tags retrace \
  --ssh-keys <SSH_KEY_ID> \
  --userdata-file cloud-init.yaml
vultr-cli instance list             # note the ID and main IP
```

Setup takes a few minutes: Docker, Node LTS, the Droid CLI, Python venv, and `swebench==5.0.2`.

## 3. Log in and set secrets
```bash
ssh root@<IP>                       # or: ssh retrace@<IP> (same key, in docker + sudo groups)
tail -f /var/log/cloud-init-output.log   # wait until /opt/retrace/READY exists
docker --version && node --version && droid --version
export FACTORY_API_KEY=fk-...       # from Factory settings → API Keys; keep it out of files in git
export HF_TOKEN=...                 # optional, avoids Hugging Face rate limits
```
PATH already includes `/opt/retrace` and the venv (from `/etc/profile.d/retrace.sh`). In a non-login shell, run `source /etc/profile.d/retrace.sh`.

## 4. Pre-pull images
```bash
cat > ~/ids.txt <<'IDS'
django__django-11099
IDS
PREPULL_JOBS=4 prepull.sh -f ~/ids.txt     # or: prepull.sh django__django-11099 sympy__sympy-20590
```
Each image is a single `swebench/sweb.eval.x86_64.<id with __ → _1776_>:latest` tag that already contains the env layers. This name rule matches the `image` column for all 500 rows of `SWE-bench/SWE-bench_Verified`.

## 5. One-task smoke test
The runner takes a `step0` job file that validates against `contracts/replay-job.schema.json`. Jobs normally come from `runs/jobs/` in the repo, which `cloud-init` clones to `/opt/retrace/repo`. For the smoke test, write a throwaway job:
```bash
cd /opt/retrace/repo && git pull
cat > ~/smoke.json <<'JOB'
{"job_id": "smoke1", "start": "step0", "task_ids": ["django__django-11099"],
 "arm": {"kind": "control"}, "model": "<model id>", "reruns": 1,
 "stop_mode": "next_user_turn", "budget_credits": 1000000}
JOB
run_job.sh ~/smoke.json 1
# → /opt/retrace/runs/smoke1/django__django-11099/1/{prompt.md,start_commit,droid.json,droid.stderr,patch.diff,pred.json,meta.json,capture/,factory-sessions/,snapshots.bundle}
#   also reachable as /opt/retrace/sessions/<job_id>-<task_id>-<trial>
grade.sh ~/smoke.json 1
# → /opt/retrace/repo/runs/results/smoke1/django__django-11099-step0-control-1.json
```
Pick `model` from the project doc (Open). Set `budget_credits` from your Factory plan. `meta.json` holds `cost_credits`, so read the real cost after the first run and set the budget from it.

What `run_job.sh` and `run_trial.sh` do:
1. `run_job.sh` validates the job, then runs every task for every rerun, trial by trial, `parallel` at a time. It skips trials that already have a `meta.json`, so a rerun resumes. It stops starting trials once the credits spent reach `budget_credits` and exits 3 if trials are left.
2. `run_trial.sh` reads `problem_statement` and `image` from the dataset. The prompt gets only the issue text, plus the hint for a `hint` arm.
3. It starts the task image with the host `droid` binary mounted read-only. For a `candidate` arm it copies `.factory/` and `AGENTS.md` from `<repo>/<arm.path>` into `/testbed`. Both paths are excluded from the patch.
4. It runs `droid exec --skip-permissions-unsafe --cwd /testbed -o json --model <job.model> -f /retrace/prompt.md`.
5. It saves `git add -A && git diff --cached <HEAD at container start>` as `model_patch`, reads `usage.factory_credits` as the cost, and removes the container. When `DROID_TIMEOUT` (default 1800 s) kills the run, `droid.json` is empty, so the cost comes from `tokenUsage.factoryCredits` in the session's `settings.json`, and `meta.json` gets `timed_out: true`.

`grade.sh` grades each trial number as its own evaluation, because the harness takes one prediction per instance:
```bash
python -m swebench.harness.run_evaluation \
  --dataset_name SWE-bench/SWE-bench_Verified \
  --predictions_path /opt/retrace/runs/<job_id>/eval-t<trial>/predictions.jsonl \
  --max_workers N --run_id t<trial>-<timestamp> --report_dir /opt/retrace/runs/<job_id>/eval-t<trial>
```
Then `retrace_job.py collect` writes `runs/results/<job_id>/<task>-step0-<arm>-<trial>.json` and validates it against `contracts/replay-result.schema.json`. A trial with an empty patch is a fail. A trial with a patch but no grader report writes no result, and `grade.sh` exits 1.

Use `SWE-bench/SWE-bench_Verified`, not `princeton-nlp/SWE-bench_Verified`. swebench 5.x needs the `image`, `eval_script` and `log_parser` columns. The princeton-nlp copy lacks them, and loading it fails with `KeyError: 'image'` (tested). Every grade run gets a fresh eval id, and a re-grade overwrites the result files.

Fields the scripts set: `model` is the job's model (passed to Droid with `--model`), `droid_version` is `droid --version` inside the container, `stop_mode` is always `next_user_turn` (the job is rejected otherwise), `evidence_role` is `final`.

Sanity check the grader with the gold patch:
```bash
python -m swebench.harness.run_evaluation --dataset_name SWE-bench/SWE-bench_Verified \
  --predictions_path gold --instance_ids django__django-11099 --max_workers 1 --run_id gold-check
```

## 5b. Checkpoint jobs (fork a recorded session)
A `checkpoint` job rewinds the recorded Droid session `session_id` to each `tool_call_ids` entry and continues it in a fresh container. The fork keeps the messages before the step's assistant message, so the step itself is replaced. The runner uses the recorded session in `/opt/retrace/sessions/<session_id>` (`factory-sessions/`, `snapshots.bundle`, `start_commit`) and the trace in `$RETRACE_REPO/runs/traces/<session_id>.json`.

The node SDK runs on the host. `replay/docker-droid.sh` is its `execPath`, and it runs `droid` inside the task container through `docker exec -i`. The task image needs no node.

An existing VM does not rerun cloud-init. Update it by hand:
```bash
cd /opt/retrace/repo && git pull
mkdir -p /opt/retrace/replay && cd recorder/replay
cp run_checkpoint.sh docker-droid.sh restore.sh fork.mjs package.json package-lock.json /opt/retrace/replay/
cp ../worker/scripts/run_job.sh ../worker/scripts/grade.sh ../worker/scripts/retrace_job.py /opt/retrace/
cd /opt/retrace/replay && npm ci --omit=dev
```
Then pull the image and run one fork:
```bash
prepull.sh django__django-11292
cat > ~/fork1.json <<'JOB'
{"job_id": "fork1", "start": "checkpoint", "session_id": "baseline1-django__django-11292-1",
 "tool_call_ids": ["toolu_01Dq3aZjyjwEvyboFYqV1dGo"], "arm": {"kind": "control"},
 "model": "claude-haiku-5-5", "reruns": 1, "stop_mode": "next_user_turn", "budget_credits": 20000}
JOB
export RETRACE_CONTINUATION='Continue.'    # test value; the control text is an open decision
run_job.sh ~/fork1.json 1
# → /opt/retrace/runs/fork1/django__django-11292/<tool_call_id>/1/{continuation.md,start_commit,fork.json,fork.stderr,patch.diff,pred.json,meta.json,capture/,factory-sessions/}
grade.sh ~/fork1.json 1
# → /opt/retrace/repo/runs/results/fork1/django__django-11292-<tool_call_id>-control-1.json
```
- A `hint` arm sends its `text` as the message. A `control` or `candidate` arm sends `RETRACE_CONTINUATION`, and `run_job.sh` stops when it is unset. A `candidate` arm copies `<repo>/<arm.path>/.factory` and `AGENTS.md` into `/testbed` before the session resumes.
- `run_job.sh` runs `tool_call_ids` x `reruns` under the same budget rule as a `step0` job. `DROID_TIMEOUT` (default 1800 s) interrupts the turn, and `meta.json` gets `timed_out: true` with the credits of the interrupted turn.
- A trial whose rewind or run fails gets `failed` in `meta.json`. `run_job.sh` runs it again on the next call. `grade.sh` writes no result for it and exits 1.
- `grade.sh` grades each (tool_call_id, trial) as its own evaluation, up to `max_workers` at once. Results have `evidence_role: "diagnosis"` and `tool_call_id`. `model` is the model the fork reported.
- `meta.json` and `fork.json` hold the successor session id, the continuation text, token counts, and `cost_credits` of the fork alone. The successor session sits in `factory-sessions/`.
- No trace is written for a fork.

Dev machines with another CPU cannot run the amd64 images with a Bun-built `droid`: it crashes under QEMU. For a local check, set `RETRACE_IMAGE` (for example `ghcr.io/epoch-research/swe-bench.eval.arm64.<instance_id>:latest`), `RETRACE_PLATFORM=linux/arm64`, and `RETRACE_DROID` to a Linux arm64 `droid` binary. Such a run does not grade.

## SWE-bench Pro

A job with `"dataset": "swebench_pro"` runs SWE-bench Pro V2 tasks (`ScaleAI/SWE-bench_Pro`, config `default`, 642 tasks). Without `dataset`, a job runs SWE-bench Verified as before. The same `run_job.sh` and `grade.sh` run both. Task ids are Pro instance ids, such as `instance_NodeBB__NodeBB-<hash>-vnan`. Scope for Retrace: the Python and Go repos (ansible, openlibrary, qutebrowser, flipt, teleport, vuls, navidrome).

### Official method
The Hugging Face dataset has no eval script. Scale ships V2 as Harbor tasks in https://github.com/scaleapi/SWE-bench_Pro-os under `v2/tasks/<instance_id>/`. Retrace uses commit `66f92766bba642462d4bbe5479e83f91f9211862` (2026-09-22, release v2.0.0). The older `swe_bench_pro_eval.py`, `run_scripts/`, `before_repo_set_cmd` and Docker Hub images are the v1 pipeline. V2 does not use them, so the runner never runs `before_repo_set_cmd`.

- Image. `docker_image` in `task.toml`: `ghcr.io/scaleapi/swe-bench_pro-v2:<instance_id>`. It is public and amd64. The image runs as root and has git and python3. It holds the repo at its base commit, with a clean tree and its history up to that commit.
- Prompt. `instruction.md`, verbatim: the PR description (problem statement), the requirements, the new interfaces, and a line that bans looking up existing solutions. It names `/app`. A `hint` arm appends `<hint>` text. The Verified prompt wording is not used.
- Repo path. `/app` (a few tasks use `/testbed`). The runner takes the first of `/app` and `/testbed` that has a `.git`. Droid runs there with `--cwd`, so the session sits in `factory-sessions/-app/`.
- Patch. `git add -A` and `git diff --cached <start commit>`, the same as Verified. The harness's own capture is `git diff --cached` in the agent sandbox.
- Grading. `grade_pro.sh` follows the harness's `patch_replay` agent. It starts a fresh container from the image, applies the patch with `git apply --verbose || git apply --3way || patch --fuzz=3 -p1`, mounts the task's `tests/` at `/tests`, and runs `bash /tests/test.sh`. `test.sh` resets test-space files, applies `test_patch.patch`, runs `run_script.sh` on `selected_test_files_to_run`, parses the output with `parser.py`, and writes `1` to `/logs/verifier/reward.txt` only if every `fail_to_pass` and `pass_to_pass` test passed. `passed` is that reward. Result files record `grader: swebench_pro`. An empty patch runs the verifier too.
- Time. `DROID_TIMEOUT` defaults to 1800 s. The harness gives 3000 s to the agent and 3000 s to the verifier. `grade_pro.sh` uses the verifier value from `task.toml`.

### Differences from the locked protocol
- The agent container has network access, because Droid must reach the Factory API. The official protocol runs the agent with `network_mode = "no-network"` and allows only the model host. A score from this runner is not comparable to the Scale leaderboard. Report it as a Retrace setup.
- Containers have no CPU or memory cap. The tasks ask for 1 CPU and 4 GB.
- Droid is not one of the harness's agents, so the run is a Retrace adapter and not a Scale-reviewed run.

### Setup
`cloud-init.yaml` clones the harness to `/opt/retrace/swe-bench-pro` (sparse, `v2/tasks` and `v2/tooling`) at the pinned commit. An existing VM needs the clone by hand:
```bash
git clone --filter=blob:none --no-checkout https://github.com/scaleapi/SWE-bench_Pro-os.git /opt/retrace/swe-bench-pro
cd /opt/retrace/swe-bench-pro && git sparse-checkout set v2/tasks v2/tooling && git checkout 66f92766bba642462d4bbe5479e83f91f9211862
```
Set `PRO_TASKS` to use another checkout (default `$RETRACE_ROOT/swe-bench-pro/v2/tasks`). Copy the new scripts as for checkpoint jobs (section 5b), plus `grade_pro.sh` and `pro_task.sh`. The Pro scripts need no extra Python package.

### Run a job
```bash
prepull.sh -f ids.txt            # Pro ids start with instance_; a full image reference also works
cat > /opt/retrace/repo/runs/jobs/pro-smoke1.json <<'JOB'
{"job_id": "pro-smoke1", "dataset": "swebench_pro", "start": "step0",
 "task_ids": ["instance_navidrome__navidrome-0a650de357babdcc8ce910fe37fee84acf4ed2fe"],
 "arm": {"kind": "control"}, "model": "claude-haiku-5-5", "reruns": 1,
 "stop_mode": "next_user_turn", "budget_credits": 40000}
JOB
run_job.sh /opt/retrace/repo/runs/jobs/pro-smoke1.json 4
grade.sh /opt/retrace/repo/runs/jobs/pro-smoke1.json 4
```
A `checkpoint` job takes the same `dataset` field and the same runners. Check a task without Droid:
```bash
grade_pro.sh <instance_id> gold  /tmp/gc/gold/<instance_id>     # reward 1
grade_pro.sh <instance_id> empty /tmp/gc/empty/<instance_id>    # reward 0
```

### Measured on the x86 worker (24 Oct 2026)
- Candidate set: `splits/pro-candidates.json`, drawn by `splits/pro_candidates.py` with seed 7. It holds 8 tasks from each of the 7 repos, each with a gold patch of 3 or more files.
- Gold patch: 56 of 56 pass. Empty patch: 56 of 56 fail. Per-task rewards, times, and image sizes are in `splits/pro-gold-check.json`. All 56 images keep the repo in `/app`. The 112 verifier runs took 22 min, 4 at a time.
- Images: 2.1 to 11.9 GB on disk each, 275 GB for the 56 (some layers are shared). The 56 pulls took 15 min with 4 at once.

| repo | image GB (min / mean / max) | pull s (mean / max) | gold verifier s (mean / max) |
|---|---|---|---|
| ansible/ansible | 2.1 / 2.1 / 2.2 | 30 / 43 | 64 / 76 |
| internetarchive/openlibrary | 2.8 / 4.1 / 4.8 | 61 / 72 | 9 / 12 |
| qutebrowser/qutebrowser | 2.1 / 2.3 / 2.7 | 27 / 39 | 17 / 30 |
| flipt-io/flipt | 2.2 / 6.4 / 8.2 | 98 / 124 | 50 / 95 |
| gravitational/teleport | 7.1 / 8.4 / 11.9 | 72 / 131 | 72 / 110 |
| future-architect/vuls | 5.4 / 6.1 / 7.0 | 81 / 117 | 108 / 187 |
| navidrome/navidrome | 4.5 / 5.0 / 5.2 | 76 / 78 | 13 / 19 |

- Droid trials (`claude-haiku-5-5`, 1 rerun, control arm, run together). A qutebrowser task (4 gold files) passed: 185 s of Droid time, 17 turns, 35 tool calls, 8,726 credits. A navidrome task (3 gold files) passed: 88 s, 12 turns, 21 tool calls, 4,026 credits. Both traces validate. Grading took 32 s and 8 s.
- A `checkpoint` fork of the navidrome trace (hint arm, one step) ran on the x86 worker with `docker-droid.sh` in `/app`, passed grading, and cost 1,574 credits.

## 6. Scale to about 8 in parallel
```bash
prepull.sh -f ~/slice.txt
run_job.sh /opt/retrace/repo/runs/jobs/<job-id>.json 8
grade.sh /opt/retrace/repo/runs/jobs/<job-id>.json 8   # harness guidance: max_workers <= 75% of cores (≤12 on 16 vCPU)
```
Use `tmux` so runs survive SSH drops. Watch `htop` and `docker stats`. If the box is CPU-bound, drop the parallel count to 6 or add a second VM. Model API rate limits may bite before CPU does. Up to `parallel` trials can overshoot the budget, because a trial is checked only when it starts.

Results land in `/opt/retrace/repo/runs/results/`. Commit and push them from the VM, or copy them back with `scp`.

## 7. Teardown (stopped instances still bill)
```bash
scp -r root@<IP>:/opt/retrace/repo/runs/results ./results-backup   # grader logs and patches: /opt/retrace/runs
vultr-cli instance list
vultr-cli instance delete <INSTANCE_ID>
```
Vultr bills stopped instances until they are destroyed. Delete the VM right after the final grade, and before the 25 Oct 9:00 AM PT deadline at the latest.

## Fallback
If account limits block you, run the same scripts on any x86_64 Ubuntu host with Docker. Options are Factory Droid Computers, BYOM (`droid computer register`, https://docs.factory.ai/droid-computers/byom), or Remote Workspaces (https://docs.factory.ai/user-guides/remote-workspaces/index).

## Tiger (results and primitives sink)

`tiger_sink.py` upserts result files and primitives files into the Tiger Postgres database. It validates each file against `contracts/` first. One run is one transaction, so a bad file writes nothing.

Setup on the worker, once per VM:
```bash
/opt/retrace/venv/bin/pip install 'psycopg[binary]'   # new VMs get it from cloud-init
export TIGER_DATABASE_URL=...        # never commit this; set it in the shell or /root/.retrace.env
```
Create the tables and roles on the database before the first run. Apply `contracts/tiger-replay-results.sql` and `contracts/tiger-primitives.sql` as the owner. Both files create the grants for `retrace_worker` and `retrace_dashboard`, so create those roles first.

Commands:
```bash
tiger_sink.py results /opt/retrace/repo/runs/results/<job-id>   # one job's result files
tiger_sink.py primitives /opt/retrace/repo/runs/primitives      # all primitives files
```
On the dev machine, set `RETRACE_REPO=$PWD RETRACE_ROOT=$PWD` first, as for `retrace_job.py`.

`grade.sh` runs `tiger_sink.py results` after each successful `collect`. It skips the step when `TIGER_DATABASE_URL` is unset. Primitives are not sent by `grade.sh`. Run `tiger_sink.py primitives` by hand.

Each upsert replaces the row with the same key. A primitives session that gets fewer calls on a re-run keeps its old extra call rows, because the role has no delete grant.

## Unverified (test on the VM)
- Checked on a live VM on 24 Oct (`vc2-16c-64gb`, sjc): cloud-init finished in 225 s (Docker 29.9.2, Droid 0.249.0, swebench 5.0.2). The gold patch resolves `django__django-11099` in 38 s. A `run_job.sh` and `grade.sh` smoke run on that task, model `gpt-6-sol`, passed: 25 s of Droid time, 25,576 `factory_credits`, one result file that validates against the schema. The image takes 4.2 GB on disk.
- Parallel run on 24 Oct: 4 tasks at once (`claude-haiku-5-5`, django and sympy) finished in 4 min 25 s with a load average of about 4.5 on 16 vCPU. 3 passed and 1 failed. The 4 trials used 21,201 factory_credits (4,277 to 7,588 each).
- Recording on 24 Oct (2 tasks, `claude-haiku-5-5`): each trial writes `runs/traces/<job_id>-<task_id>-<trial>.json`, which validates against `contracts/trace.schema.json`. In a fresh task container, `git fetch` of the trial's `snapshots.bundle` and `restore.sh <last snapshot_ref>` reproduce the graded `patch.diff` byte for byte on both tasks.
- Untested: a non-root user inside the task container, and 8 trials at once.
- Checkpoint forks ran on 24 Oct on a dev machine (arm64 image, Droid 0.249.0, `claude-haiku-5-5`): `control`, `hint`, and `candidate` arms, one timeout, and one rewind failure. They used about 11,600 credits. Untested on the x86 VM: the amd64 image with `docker-droid.sh`, `grade.sh` on a fork, and several forks at once.
- Whether Droid finds the `testbed` conda env from the prompt hint alone.
- Whether `usage.factory_credits` in the `droid exec` JSON is the full cost of the trial, and matches `tokenUsage.factoryCredits` from the SDK.
- Whether Droid uses the model passed with `--model`. The result records the job's `model`, not a value read back from Droid.
- Wall time per task and the CPU load of 8 parallel runs.
