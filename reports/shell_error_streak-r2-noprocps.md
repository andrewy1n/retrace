# shell_error_streak-r2-noprocps

Evidence: step-0 `final` results.

## Setup

- Model: claude-haiku-5-5. Droid: 0.249.0. Grader: swebench_pro.
- Arms: A = r2-heldout-a; C = r2-heldout-shell-fallback.
- Checkout (`repo_sha`): 094c707ebc26, c6892adbd519.
- Control: A. Trials killed by the timeout are counted apart and left out of credits.

## Arms

| Arm | Tasks | Trials | Passed | Pass rate (95% Wilson) | Timed out | Credits | Credits per trial | shell_error_streak runs |
|---|---|---|---|---|---|---|---|---|
| A | 4 | 8 | 7 | 87.5% (52.9% to 97.8%) | 0 | 90,104 | 11,263 | 8 of 8 (100.0%; 67.6% to 100.0%) |
| C | 4 | 8 | 8 | 100.0% (67.6% to 100.0%) | 0 | 90,762 | 11,345 | 1 of 8 (12.5%; 2.2% to 47.1%) |

## Paired differences

### C against A

Tasks in both arms: 4. Left out: 0.

- Pass rate difference (C minus A): +12.5 points (95% interval +0.0 to +37.5).
- Tasks where only A passes every rerun: 0. Only C: 1. Exact McNemar p = 1.000.
- Credits, geometric-mean ratio C to A: 1.071 (95% interval 0.956 to 1.199) over 4 tasks.
- shell_error_streak incidence difference (C minus A), share of a task's runs, over 4 tasks with primitives in both arms: -87.5 points (95% interval -100.0 to -62.5).
- Tasks where only A shows shell_error_streak in some run: 3. Only C: 0. Exact McNemar p = 0.250.
- Mean shell_error_streak count difference (C minus A), paired by task, over 4 tasks: -3.9 calls (95% interval -5.5 to -2.2).
- Bootstrap intervals rest on 4 tasks. With fewer than 10 tasks they say little.

## Verification after the last edit

Runs with a successful edit call. A run skips verification when no test command follows its last edit.

| Arm | Runs with primitives | Runs with an edit | Skipped verification (95% Wilson) | Test commands after the last edit, mean |
|---|---|---|---|---|
| A | 8 | 8 | 1 of 8 (12.5%; 2.2% to 47.1%) | 1.62 |
| C | 8 | 8 | 5 of 8 (62.5%; 30.6% to 86.3%) | 0.75 |

## Proxy agreement

Agreement with the dataset grader on final trials. For verification only; the improvement loop never reads it.

No final trial has proxies.

## Round 2 context

- Secondary breakdown named in Amendment 1 of `reports/preregistration-r2.md`: the 4 held-out tasks whose image lacks `ps` (`splits/pro-heldout2-noprocps.json`), all qutebrowser. On these images Droid 0.249.0 reports every foreground `Execute` call as killed by SIGKILL. `shell-fallback` is a workaround for that Droid defect.
- Round 2 tested 2 candidates. The time gap and the run order are in `reports/shell_error_streak-r2.md`.
