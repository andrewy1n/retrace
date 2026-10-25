# large_root_searches-r2

Evidence: step-0 `final` results.

## Setup

- Model: claude-haiku-5-5. Droid: 0.249.0. Grader: swebench_pro.
- Arms: A = r2-heldout-a; C = r2-heldout-root-search-limit.
- Checkout (`repo_sha`): 094c707ebc26, 6f9ba338e9de, c6892adbd519.
- Control: A. Trials killed by the timeout are counted apart and left out of credits.

## Arms

| Arm | Tasks | Trials | Passed | Pass rate (95% Wilson) | Timed out | Credits | Credits per trial | large_root_searches runs |
|---|---|---|---|---|---|---|---|---|
| A | 24 | 48 | 44 | 91.7% (80.4% to 96.7%) | 1 | 384,056 | 8,171 | 5 of 48 (10.4%; 4.5% to 22.2%) |
| C | 24 | 48 | 46 | 95.8% (86.0% to 98.8%) | 1 | 392,291 | 8,347 | 0 of 48 (0.0%; 0.0% to 7.4%) |

## Paired differences

### C against A

Tasks in both arms: 24. Left out: 0.

- Pass rate difference (C minus A): +4.2 points (95% interval +0.0 to +10.4).
- Tasks where only A passes every rerun: 0. Only C: 2. Exact McNemar p = 0.500.
- Credits, geometric-mean ratio C to A: 1.084 (95% interval 1.002 to 1.172) over 24 tasks.
- large_root_searches incidence difference (C minus A), share of a task's runs, over 24 tasks with primitives in both arms: -10.4 points (95% interval -20.8 to -2.1).
- Tasks where only A shows large_root_searches in some run: 4. Only C: 0. Exact McNemar p = 0.125.
- Mean large_root_searches count difference (C minus A), paired by task, over 24 tasks: -0.1 calls (95% interval -0.2 to -0.0).

## Verification after the last edit

Runs with a successful edit call. A run skips verification when no test command follows its last edit.

| Arm | Runs with primitives | Runs with an edit | Skipped verification (95% Wilson) | Test commands after the last edit, mean |
|---|---|---|---|---|
| A | 48 | 48 | 3 of 48 (6.2%; 2.1% to 16.8%) | 1.90 |
| C | 48 | 48 | 2 of 48 (4.2%; 1.2% to 14.0%) | 1.75 |

## Proxy agreement

Agreement with the dataset grader on final trials. For verification only; the improvement loop never reads it.

| Arm | Proxy | Usable | Excluded | Proxy pass, grader pass | Proxy pass, grader fail | Proxy fail, grader pass | Proxy fail, grader fail | Agreement (95% Wilson) | Kappa | Precision of proxy pass (95% Wilson) |
|---|---|---|---|---|---|---|---|---|---|---|
| A | repo_tests | 37 | 11 | 20 | 1 | 14 | 2 | 59.5% (43.5% to 73.7%) | 0.09 | 95.2% (77.3% to 99.2%) |
| A | acceptance | 0 | 48 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| A | last_test_exit | 38 | 10 | 35 | 3 | 0 | 0 | 92.1% (79.2% to 97.3%) | 0.00 | 92.1% (79.2% to 97.3%) |
| A | combined | 0 | 48 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| C | repo_tests | 36 | 12 | 20 | 0 | 14 | 2 | 61.1% (44.9% to 75.2%) | 0.14 | 100.0% (83.9% to 100.0%) |
| C | acceptance | 0 | 48 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| C | last_test_exit | 39 | 9 | 37 | 2 | 0 | 0 | 94.9% (83.1% to 98.6%) | 0.00 | 94.9% (83.1% to 98.6%) |
| C | combined | 0 | 48 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| all | repo_tests | 73 | 23 | 40 | 1 | 28 | 4 | 60.3% (48.8% to 70.7%) | 0.11 | 97.6% (87.4% to 99.6%) |
| all | acceptance | 0 | 96 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| all | last_test_exit | 77 | 19 | 72 | 5 | 0 | 0 | 93.5% (85.7% to 97.2%) | 0.00 | 93.5% (85.7% to 97.2%) |
| all | combined | 0 | 96 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |

## Round 2 context

- Round 2 tested 2 candidates, `shell-fallback` and `root-search-limit`, against one shared arm A (`reports/preregistration-r2.md`). No claim compares the two candidates.
- Time gap. Arm A trials finished between 08:00 and 09:36 UTC on 2026-10-25. Each candidate arm's trials finished between 08:11 and 10:08 UTC, so up to about 1.5 hours after arm A. All arms used the same model, Droid version, settings, and worker, and they overlapped in time.
- The 3 replacement tasks of Amendment 2 ran in a resumed job, after each arm's other tasks: arm A from 09:07 to 09:36 UTC, the candidate arms from 09:47 to 10:08 UTC.
- For a short period the worker ran about 15 trials at once and its load reached about 110. The regression candidate jobs were stopped and restarted. Each held-out arm has 1 trial killed by the timeout.
