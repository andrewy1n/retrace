# Retrace: benchmark plan (initial)

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
| Docker | Required. Official images are amd64 only. Mac arm64 support was closed "not planned"; run on x86 Linux |
| Image size | About 1 to 1.3 GB per task (compressed). matplotlib about 3 GB (skip), xarray about 2 GB, sklearn about 1.6 GB |
| Disk | 35 light-repo tasks about 20 to 40 GB compressed (estimate). Budget 60 to 100 GB free |
| Grading | JSONL `{"instance_id", "model_name_or_path", "model_patch"}` then `swebench eval` or `python -m swebench.harness.run_evaluation`. Use a fresh `run_id` per re-grade |
| Hidden tests | `FAIL_TO_PASS`, `PASS_TO_PASS`, `test_patch` are in the dataset. The agent must only get `problem_statement` and `base_commit` |
| Test edits | Grader resets files touched by the official test patch, then applies its own. Edits to other files (for example `conftest.py`) are not reset |
| Cost | Secondhand figure (Vals): Factory harness about $1.13 and 6m50s per task. Credit-to-dollar conversion unknown |

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

The run order and the budget are in the Now section of the project doc.

## What we can claim
- A held-out set of about 14 tasks only shows large effects. Report counts, sample size, and an interval. A small or negative result is reported as such.
- Test tampering does not inflate SWE-bench scores (the grader resets those files). Present the "block edits to test files" hook as a **behavior guardrail demo** (agent fixes the source instead of weakening the assertion), not as a score lever.
- Some failures may be benchmark artifacts (OpenAI reported flawed tests in many Verified tasks).

## Risks
- Test tampering may be rare in Droid sessions on SWE-bench. Check on the first batch; have a second failure type ready (for example wrong-file edits).
- At about 76% pass rate (Vals, GPT 5.5) there are only about 8 failures in 35 tasks. A cheaper model gives more failures but more benchmark-artifact noise.
- No official recipe for `droid exec` on SWE-bench. Harbor (Terminal-Bench 2.0 framework) has a Verified adapter but no pre-integrated Droid agent.
- Image downloads are large. Pull before the event or early.

## Fallbacks
- **Verified Mini** (django 25, sphinx 25): mine on django, hold out sphinx. One held-out repo only.
- **Terminal-Bench**: has an existing Droid integration pattern, but tasks are not repo-based, so "unseen repos" and regression sets are harder.

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
