# Retrace on Vultr: replay/grading worker

One x86_64 VM runs `droid exec` inside the official SWE-bench Verified images and grades the patches with the official harness. Laptops (Windows/WSL, Mac) can't do this well because the images are amd64 only.

Files:
- `cloud-init.yaml`: user data for the VM (generated, do not hand-edit)
- `scripts/prepull.sh`, `run_job.sh`, `run_trial.sh`, `grade.sh`, `retrace_job.py`: installed to `/opt/retrace/`
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
grade.sh ~/smoke.json 1
# → /opt/retrace/repo/runs/results/smoke1/django__django-11099-step0-control-1.json
```
Pick `model` from the project doc (Open). Set `budget_credits` from your Factory plan. `meta.json` holds `cost_credits`, so read the real cost after the first run and set the budget from it.

What `run_job.sh` and `run_trial.sh` do:
1. `run_job.sh` validates the job, then runs every task for every rerun, trial by trial, `parallel` at a time. It skips trials that already have a `meta.json`, so a rerun resumes. It stops starting trials once the credits spent reach `budget_credits` and exits 3 if trials are left.
2. `run_trial.sh` reads `problem_statement` and `image` from the dataset. The prompt gets only the issue text, plus the hint for a `hint` arm.
3. It starts the task image with the host `droid` binary mounted read-only. For a `candidate` arm it copies `.factory/` and `AGENTS.md` from `<repo>/<arm.path>` into `/testbed`. Both paths are excluded from the patch.
4. It runs `droid exec --skip-permissions-unsafe --cwd /testbed -o json --model <job.model> -f /retrace/prompt.md`.
5. It saves `git add -A && git diff --cached <HEAD at container start>` as `model_patch`, reads `usage.factory_credits` as the cost, and removes the container.

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

## Unverified (test on the VM)
- Checked on a live VM on 24 Oct (`vc2-16c-64gb`, sjc): cloud-init finished in 225 s (Docker 29.9.2, Droid 0.249.0, swebench 5.0.2). The gold patch resolves `django__django-11099` in 38 s. A `run_job.sh` and `grade.sh` smoke run on that task, model `gpt-6-sol`, passed: 25 s of Droid time, 25,576 `factory_credits`, one result file that validates against the schema. The image takes 4.2 GB on disk.
- Parallel run on 24 Oct: 4 tasks at once (`claude-haiku-5-5`, django and sympy) finished in 4 min 25 s with a load average of about 4.5 on 16 vCPU. 3 passed and 1 failed. The 4 trials used 21,201 factory_credits (4,277 to 7,588 each).
- Recording on 24 Oct (2 tasks, `claude-haiku-5-5`): each trial writes `runs/traces/<job_id>-<task_id>-<trial>.json`, which validates against `contracts/trace.schema.json`. In a fresh task container, `git fetch` of the trial's `snapshots.bundle` and `restore.sh <last snapshot_ref>` reproduce the graded `patch.diff` byte for byte on both tasks.
- Untested: a non-root user inside the task container, 8 trials at once, and the `candidate` and `hint` arms.
- Whether Droid finds the `testbed` conda env from the prompt hint alone.
- Whether `droid exec -o json` writes partial output when `DROID_TIMEOUT` (default 1800 s) kills it. Until then a killed trial records `cost_credits` 0, which undercounts the budget.
- Whether `usage.factory_credits` in the `droid exec` JSON is the full cost of the trial, and matches `tokenUsage.factoryCredits` from the SDK.
- Whether Droid uses the model passed with `--model`. The result records the job's `model`, not a value read back from Droid.
- Wall time per task and the CPU load of 8 parallel runs.
