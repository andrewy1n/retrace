# Pre-registration, round 2

Round 2 tests new targets from discovery round 2. Each target has its own candidate. All candidates share one control arm and one new held-out set. `reports/preregistration.md` stays the record for round 1 (`calls_before_first_edit`). Its rules apply here unless this file says otherwise.

## Setup

| Item | Value |
|---|---|
| Targets | Set in Amendment 1 of this file, before any candidate runs on held-out or regression tasks |
| Dataset | SWE-bench Pro V2 (`ScaleAI/SWE-bench_Pro`, config `default`), job `dataset` `swebench_pro` |
| Derivation | The 21 `derivation` tasks of `splits/calls_before_first_edit.json`, control step-0 sessions only |
| Held-out | `splits/pro-heldout2.json`: up to 8 new tasks from each held-out repo (qutebrowser, navidrome, vuls), drawn by `splits/pro_heldout2.py` from the seeded order of `splits/pro_candidates.py`, past the round-1 tasks, gold-checked in `splits/pro-heldout2-gold-check.json`. No agent ran any of them before the draw |
| Regression | The 8 `regression` tasks of `splits/calls_before_first_edit.json` |
| Splits | `splits/<target>.json` per target, with the derivation, held-out, and regression lists above |
| Model | `claude-haiku-5-5` |
| Droid version | 0.249.0 |
| Reruns per task per arm | 2 |
| Grader | The SWE-bench Pro V2 verifier (`swebench_pro`), as in round 1 |

| Arm | Job ids | Harness |
|---|---|---|
| A | `r2-heldout-a`, `r2-regression-a` | Unmodified Droid. Shared by every round-2 candidate |
| one per target | `r2-heldout-<id>`, `r2-regression-<id>` | `analysis/proposals/<id>`, frozen (`FROZEN.md`) before its first held-out or regression run |

Arm A starts before the targets are fixed. It does not depend on the target. The analysis role never reads held-out or regression sessions, results, or primitives. Candidate arms run later than arm A, with the same model, settings, Droid version, and worker. Each report states the time gap.

No arm runs `explore-budget`. Round 2 compares each candidate with unmodified Droid only. No claim compares two candidates.

## Primary outcome

Per target, the incidence of the targeted behaviour per run on held-out tasks, from a hard signal over primitives with a fixed threshold. Amendment 1 gives each rule. A signal with a count also gets the mean count difference, paired by task.

## Secondary outcomes

As in `reports/preregistration.md`: held-out pass rate, regression pass rate (one regression task that A passes in every rerun and the candidate fails in any rerun counts as harm), Factory credits paired by task (geometric-mean ratio), and test commands after the last source edit.

## Proxies

As in `reports/preregistration.md`. No task has an acceptance check, so `acceptance` and `combined` give no verdict. Round 1 measured `repo_tests` as weak on the held-out repos, so the proxy guard is `last_test_exit`, with `repo_tests` reported next to it.

## Analysis

As in `reports/preregistration.md`. Each candidate gets its own report, `reports/<target>-r2.md` and `reports/<target>-r2-regression.md`, written by `recorder/replay/report.py`. Several targets are tested at once, so each report states how many candidates round 2 tested. A small or negative result is reported as such. A candidate with no credit gain or with regression harm gets no pull request.

## Amendments

### Amendment 1, 2026-10-25: the round-2 targets

Made after discovery round 2 (5d3cb75) and before any candidate runs on held-out or regression tasks. Arm A had started. Nobody in the analysis role read its sessions or results.

Discovery round 2 tested 2 candidates. Neither target passes the out-of-task promotion rule of `analysis/AGENTS.md` (each varies within only a few derivation tasks). Both were promoted by count times cost. The splits are `splits/shell_error_streak.json` and `splits/large_root_searches.json`.

| Target | Candidate | Hard signal |
|---|---|---|
| `shell_error_streak` | `analysis/proposals/shell-fallback` | The run has 3 or more errored `Execute` calls that each directly follow an errored `Execute` call, from primitives (`shell_error_streak` in `recorder/replay/report.py`). The count is reported with it. |
| `large_root_searches` | `analysis/proposals/root-search-limit` | The run has at least 1 search call over the whole repo (primitives `files` is `["."]`) whose `output_tokens_est` is over 2,000 (`large_root_searches` in `recorder/replay/report.py`). The count is reported with it. |

`shell_error_streak` comes from a Droid 0.249.0 defect, not from the model: in an image without `ps`, every foreground `Execute` call is reported as killed by SIGKILL (root `AGENTS.md`, Environment). 4 of the 8 qutebrowser held-out images lack `ps`, and none of the navidrome or vuls images. The image property was read before any candidate run. It reads no outcome. The `shell-fallback` report also gives each result on the held-out tasks whose image lacks `ps`, as a secondary breakdown.

### Amendment 2, 2026-10-25: 3 held-out tasks have Alpine images

Found when arm A ran, before any candidate result on these tasks existed. 3 tasks of `splits/pro-heldout2.json` (`vuls-e1fab805`, `vuls-ef2be3d6`, `navidrome-66b74c81`) have Alpine (musl) images. The glibc Droid binary does not start there (`exec /usr/local/bin/droid: no such file or directory`), so no arm can produce a result on them. They leave every comparison, as the Alpine teleport tasks left the pool in round 1. The held-out comparison has 21 tasks: 8 qutebrowser, 7 navidrome, 6 vuls. The decision reads no outcome, since these trials wrote no result.
