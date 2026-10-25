# file_rereads-r3-regression

Evidence: step-0 `final` results.

## Setup

- Model: claude-haiku-5-5. Droid: 0.249.0. Grader: swebench_pro.
- Arms: A = r2-regression-a; C = r3-regression-read-whole-file.
- Checkout (`repo_sha`): 2da0880a9e55, bb9cfee3e881.
- Control: A. Trials killed by the timeout are counted apart and left out of credits.

## Arms

| Arm | Tasks | Trials | Passed | Pass rate (95% Wilson) | Timed out | Credits | Credits per trial | file_rereads runs |
|---|---|---|---|---|---|---|---|---|
| A | 8 | 16 | 15 | 93.8% (71.7% to 98.9%) | 0 | 199,028 | 12,439 | 7 of 16 (43.8%; 23.1% to 66.8%) |
| C | 8 | 16 | 16 | 100.0% (80.6% to 100.0%) | 0 | 195,453 | 12,216 | 10 of 15 (66.7%; 41.7% to 84.8%, 1 without primitives) |

## Paired differences

### C against A

Tasks in both arms: 8. Left out: 0.

- Pass rate difference (C minus A): +6.2 points (95% interval +0.0 to +18.8).
- Tasks where only A passes every rerun: 0. Only C: 1. Exact McNemar p = 1.000.
- Credits, geometric-mean ratio C to A: 1.056 (95% interval 0.908 to 1.245) over 8 tasks.
- file_rereads incidence difference (C minus A), share of a task's runs, over 8 tasks with primitives in both arms: +25.0 points (95% interval +6.2 to +50.0).
- Tasks where only A shows file_rereads in some run: 0. Only C: 2. Exact McNemar p = 0.500.
- Mean file_rereads count difference (C minus A), paired by task, over 8 tasks: -1.1 calls (95% interval -4.1 to +1.2).
- Bootstrap intervals rest on 8 tasks. With fewer than 10 tasks they say little.

## Verification after the last edit

Runs with a successful edit call. A run skips verification when no test command follows its last edit.

| Arm | Runs with primitives | Runs with an edit | Skipped verification (95% Wilson) | Test commands after the last edit, mean |
|---|---|---|---|---|
| A | 16 | 16 | 2 of 16 (12.5%; 3.5% to 36.0%) | 1.75 |
| C | 15 | 15 | 2 of 15 (13.3%; 3.7% to 37.9%) | 1.27 |

## Proxy agreement

Agreement with the dataset grader on final trials. For verification only; the improvement loop never reads it.

| Arm | Proxy | Usable | Excluded | Proxy pass, grader pass | Proxy pass, grader fail | Proxy fail, grader pass | Proxy fail, grader fail | Agreement (95% Wilson) | Kappa | Precision of proxy pass (95% Wilson) |
|---|---|---|---|---|---|---|---|---|---|---|
| A | repo_tests | 16 | 0 | 10 | 0 | 5 | 1 | 68.8% (44.4% to 85.8%) | 0.20 | 100.0% (72.2% to 100.0%) |
| A | acceptance | 0 | 16 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| A | last_test_exit | 12 | 4 | 11 | 1 | 0 | 0 | 91.7% (64.6% to 98.5%) | 0.00 | 91.7% (64.6% to 98.5%) |
| A | combined | 0 | 16 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| C | repo_tests | 16 | 0 | 10 | 0 | 6 | 0 | 62.5% (38.6% to 81.5%) | 0.00 | 100.0% (72.2% to 100.0%) |
| C | acceptance | 0 | 16 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| C | last_test_exit | 12 | 4 | 12 | 0 | 0 | 0 | 100.0% (75.7% to 100.0%) | n/a | 100.0% (75.7% to 100.0%) |
| C | combined | 0 | 16 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| all | repo_tests | 32 | 0 | 20 | 0 | 11 | 1 | 65.6% (48.3% to 79.6%) | 0.10 | 100.0% (83.9% to 100.0%) |
| all | acceptance | 0 | 32 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| all | last_test_exit | 24 | 8 | 23 | 1 | 0 | 0 | 95.8% (79.8% to 99.3%) | 0.00 | 95.8% (79.8% to 99.3%) |
| all | combined | 0 | 32 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |

## Round 3 context

- Round 3 tested 1 candidate, `read-whole-file`, against the round-2 arm A (`reports/preregistration-r2.md`, Amendment 3).
- Time gap. Arm A trials finished between 07:45 and 08:09 UTC on 2026-10-25. Arm C trials finished between 11:16 and 11:38 UTC, about 3.5 hours after arm A.
- One arm C trial (`ansible-d6d22519`, trial 2) has no `session_id` and no primitives. Its trial directory holds two Droid sessions, and primitives were not written for it. Its grade and credits count.
