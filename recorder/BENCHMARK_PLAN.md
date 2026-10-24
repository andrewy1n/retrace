# Retrace: benchmark plan (initial)

Status: draft, updated 23 Oct 2026. Nothing below has run on SWE-bench images yet. Items marked **Unverified** need a test on day one.

## Decision
Use **SWE-bench Verified** (500 tasks, 12 repos), a slice of about 36 to 40 tasks, run with Factory Droid (`droid exec`) on **x86 Linux**. Fallback: **Verified Mini** (50 tasks, django + sphinx).

## Why SWE-bench Verified
- Each task has a repo, an issue, and an automatic pass/fail grader, so replay outcomes are objective and need no hand labeling.
- Tasks are public, which suits a public repo.
- Many repos, so we can hold out whole repos for the "unseen repos" claim.

## Facts checked
| Item | Finding |
|---|---|
| Size | 500 tasks, 12 repos |
| Repo counts | django 231, sympy 75, sphinx 44, matplotlib 34, scikit-learn 32, astropy 22, xarray 22, pytest 19, pylint 10, requests 8, seaborn 2, flask 1 |
| Docker | Required. Official images are amd64 only. Mac arm64 support was closed "not planned"; run on x86 Linux. Epoch AI publishes arm64 builds (`ghcr.io/epoch-research/swe-bench.eval.arm64.<id>:latest`, 1819 of 2294 instances listed, untested). They are a fallback for the arm64 laptop |
| Image size | About 1 to 1.3 GB per task (compressed); `django__django-11099` takes 4.2 GB on disk. matplotlib about 3 GB (skip), xarray about 2 GB, sklearn about 1.6 GB |
| Disk | 35 light-repo tasks about 20 to 40 GB compressed (estimate). Budget 60 to 100 GB free |
| Grading | JSONL `{"instance_id", "model_name_or_path", "model_patch"}` then `swebench eval` or `python -m swebench.harness.run_evaluation`. Use a fresh `run_id` per re-grade |
| Hidden tests | `FAIL_TO_PASS`, `PASS_TO_PASS`, `test_patch` are in the dataset. The agent must only get `problem_statement` and `base_commit` |
| Test edits | Grader resets files touched by the official test patch, then applies its own. Edits to other files (for example `conftest.py`) are not reset |
| Cost | Secondhand figure (Vals): Factory harness about $1.13 and 6m50s per task. Credit-to-dollar conversion unknown. Andrew has a free $20 Factory plan, which likely covers far fewer than the planned runs. One easy task (`django__django-11099`, `gpt-6-sol`) cost 25,576 factory_credits |
| Model | `droid exec` 0.248.0 defaults to `gpt-6-sol`. The Vals figures are for GPT 5.5. All runs use `claude-haiku-5-5` (project doc, Decided 2026-10-24). A 4-task check (24 Oct, one trial each, django and sympy) passed 3 of 4 and used 21,201 factory_credits, about 5,300 per task, against 25,576 for `gpt-6-sol` on one easy task |

## Slice and split (split by repo, not by task)
| Set | Size | Repos | Use |
|---|---|---|---|
| Dev | about 18 | django about 10, sympy about 8 | Record sessions, label failures, replay, derive the change |
| Held-out | about 14 | pytest about 5, astropy about 4, pylint about 3, requests about 2 to 3 (optionally a few sphinx) | Never studied before the change is frozen |
| Regression | about 8 to 10 | tasks the baseline already passes, from dev repos | Check the change does not break passing tasks |

Task selection rules:
- Skip matplotlib, xarray, scikit-learn (large images).
- Prefer tasks in the 15 min to 1 h difficulty band.
- Run the gold patch first and drop any task that fails with it.
- Keep tasks where one baseline run fails or looks borderline; always-pass or always-fail tasks give replay nothing to flip.
- Commit `splits/` before anyone studies held-out tasks.

## Process
1. **Smoke test (first checkpoint).** One task end to end: start the task image, run `droid exec` inside it (repo at `/testbed`), take `git diff` as `model_patch`, grade it. Checked 24 Oct on the Vultr VM: the host binary runs as root in the SWE-bench image, authenticates, and one `django__django-11099` trial graded as a pass. **Unverified:** a non-root test user. Droid needs a glibc image (the SWE-bench base is Ubuntu 22.04).
2. **Rewind:** `session.rewind` restores only the file snapshots passed to it (`@factory/droid-sdk` 0.10.0). Git snapshots are the source of truth. The runner calls `recorder/replay/restore.sh <snapshot_ref>` after rewind. A live check of the installed CLI is still open.
3. Baseline pass over the whole slice, one run per task.
4. Record sessions, label failures, pick the biggest failure group. Every `run_trial.sh` run records a trace (`runs/traces/<job_id>-<task_id>-<trial>.json`), a snapshot bundle and the Droid session.
5. Replay 3 to 5 checkpoints with reruns, a no-hint control, and the hint ladder.
6. Generalize, leak-check, freeze the candidate.
7. Run held-out and regression fresh from step 0 with the frozen change. Held-out has three arms: (A) unmodified Droid, (B) a change an LLM proposes from the same transcripts, (C) the replay-derived change. Use several seeds, paired per task.

## Budget (rough, unmeasured)
About $1 and 7 minutes per run.

| Phase | Runs | Cost |
|---|---|---|
| Baseline, about 35 tasks | 35 | about $35 to 40 |
| Replays | 40 to 60 | about $30 to 60 |
| Held-out validation (about 15 tasks, arms A, B and C, 2 seeds) | 90 | about $90 |
| Regression (about 12 tasks, 2 conditions) | 25 to 30 | about $25 to 30 |
| **Total** | about 190 to 215 | **about $180 to 220** |

The dollar figures are guesses. The contract counts Factory credits (`cost_credits`), and the credit-to-dollar rate is unmeasured. Measure credits on the smoke test and rescale this table before the baseline.

With 8 parallel containers, about 3 to 4 hours of runs plus image pulls.

## What we can claim
- A held-out set of about 14 tasks only shows large effects. Report counts, sample size, and an interval. A small or negative result is reported as such.
- Test tampering does not inflate SWE-bench scores (the grader resets those files). Present the "block edits to test files" hook as a **behavior guardrail demo** (agent fixes the source instead of weakening the assertion), not as a score lever.
- Some failures may be benchmark artifacts (OpenAI reported flawed tests in many Verified tasks).

## Risks
- Test tampering may be rare in Droid sessions on SWE-bench. Check on the first batch; have the second candidate ready: skipped verification (Droid finishes without a test run after its last source edit), with a Stop hook as the change.
- At about 76% pass rate (Vals, GPT 5.5; Haiku should fail more) there are only about 8 failures in 35 tasks. A cheaper model gives more failures but more benchmark-artifact noise.
- No official recipe for `droid exec` on SWE-bench. Harbor (Terminal-Bench 2.0 framework) has a Verified adapter but no pre-integrated Droid agent.
- Image downloads are large. Pull before the event or early.

## Fallbacks
- **Verified Mini** (django 25, sphinx 25): mine on django, hold out sphinx. One held-out repo only.
- **Terminal-Bench**: has an existing Droid integration pattern, but tasks are not repo-based, so "unseen repos" and regression sets are harder.

## Compute on Vultr
Setup, scripts and exact commands are in [worker/README.md](worker/README.md).

- **Why:** SWE-bench images are amd64 only, and our laptops are Windows/WSL or Mac. One x86_64 VM runs Droid and the grader side by side. This also counts toward MLH "Best Use of Vultr".
- **Machine:** `vc2-16c-64gb` in `sjc` (16 shared vCPU, 64 GB RAM, 1280 GB SSD, **$0.438/hr**), Ubuntu 24.04 (os id 2284). The disk covers the 60 to 100 GB image budget many times over. Upgrade to dedicated `voc-g-16c-64gb-320s-amd` ($0.658/hr in the API) if shared CPU is noisy.
- **Parallelism:** about 8 Droid containers at once, then grading with `--max_workers 8` (harness guidance: at most 75% of cores, so 12 or fewer). 215 runs × 7 min ≈ 25 agent-hours, so about 3 hours wall time at 8 in parallel, plus pulls and grading. Same as the 3 to 4 hours above. **Unverified:** CPU load per run.
- **Cost:** 24 h ≈ $10.50 per VM. The full weekend (about 36 h) ≈ $16. A second VM doubles this. Andrew has $100 of Vultr credit; the account is awaiting verification (23 Oct).
- **Harness version:** pin `swebench==5.0.2` and use dataset `SWE-bench/SWE-bench_Verified`. The `princeton-nlp/SWE-bench_Verified` copy lacks the `image`/`eval_script` columns 5.x needs (`KeyError: 'image'`, tested).
- **Labeling (optional):** Vultr Serverless Inference is OpenAI-compatible (`https://api.vultrinference.com/v1`). It could run the cheap failure labeler. **Unverified:** pricing. Vultr's pages disagree (catalog says `deepseek-v4.1-flash` $0.15/$0.60 per 1M in/out, an older doc says $0.55/$2.75). Check in the console before relying on it.
- **Factory tie-in:** the VM can be registered as a Droid computer via BYOM (`droid computer register`).
- **Risk: account limits.** New accounts have instance-count and cost caps, and increases need a ticket. Check Billing → Limits right after sign-up. Fallback: Factory Droid Computers or Remote Workspaces, or any x86_64 Docker host with the same scripts.
- **Teardown:** stopped instances still bill. Run `vultr-cli instance delete <id>` after the final grade.

## Sources
- SWE-bench Verified dataset: https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified
- Evaluation guide: https://www.swebench.com/SWE-bench/guides/evaluation/
- Epoch AI optimized images: https://epoch.ai/latest/swebench-docker
- Mac arm64 issue (closed, not planned): https://github.com/SWE-bench/SWE-bench/issues/375
- Droid exec: https://docs.factory.com/droid-exec/overview
- Droid hooks: https://docs.factory.com/harness/hooks
- Vals SWE-bench page: https://www.vals.ai/benchmarks/swebench
- NIST on test-edit cheating: https://www.nist.gov/caissi/2-examples-cheating-caisis-agent-evaluations
- OpenAI on retiring Verified: https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
- Verified Mini: https://huggingface.co/datasets/MariusHobbhahn/swe-bench-verified-mini
- Vultr pricing: https://www.vultr.com/pricing/
- Vultr plans API (plan IDs, hourly prices, regions): https://api.vultr.com/v2/plans
- Vultr FAQ (billing, promo codes, limits, stopped instances): https://www.vultr.com/resources/faq/
- Vultr account limits: https://docs.vultr.com/platform/billing/manage-account-limits
- Vultr CLI: https://github.com/vultr/vultr-cli
- Vultr Serverless Inference docs: https://api.vultrinference.com/docs
- MLH Vultr credits: https://www.mlh.com/partners/vultr
- Factory BYOM: https://docs.factory.ai/droid-computers/byom
- SWE-bench Verified (harness 5.x dataset): https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified
