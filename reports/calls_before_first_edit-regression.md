# calls_before_first_edit-regression

Evidence: step-0 `final` results.

## Setup

- Model: claude-haiku-5-5. Droid: 0.249.0. Grader: swebench_pro.
- Arms: A = final1-regression-a; C = final1-regression-c.
- Checkout (`repo_sha`): d4f304b6f4a7.
- Control: A. Trials killed by the timeout are counted apart and left out of credits.

## Arms

| Arm | Tasks | Trials | Passed | Pass rate (95% Wilson) | Timed out | Credits | Credits per trial | calls_before_first_edit runs |
|---|---|---|---|---|---|---|---|---|
| A | 8 | 16 | 15 | 93.8% (71.7% to 98.9%) | 0 | 203,486 | 12,718 | 9 of 16 (56.2%; 33.2% to 76.9%) |
| C | 8 | 16 | 16 | 100.0% (80.6% to 100.0%) | 0 | 128,368 | 8,023 | 0 of 16 (0.0%; 0.0% to 19.4%) |

## Paired differences

### C against A

Tasks in both arms: 8. Left out: 0.

- Pass rate difference (C minus A): +6.2 points (95% interval +0.0 to +18.8).
- Tasks where only A passes every rerun: 0. Only C: 1. Exact McNemar p = 1.000.
- Credits, geometric-mean ratio C to A: 0.782 (95% interval 0.618 to 0.998) over 8 tasks.
- calls_before_first_edit incidence difference (C minus A), share of a task's runs, over 8 tasks with primitives in both arms: -56.2 points (95% interval -87.5 to -25.0).
- Tasks where only A shows calls_before_first_edit in some run: 5. Only C: 0. Exact McNemar p = 0.062.
- Mean calls_before_first_edit count difference (C minus A), paired by task, over 8 tasks: -4.6 calls (95% interval -9.6 to +0.0).
- Bootstrap intervals rest on 8 tasks. With fewer than 10 tasks they say little.

## Verification after the last edit

Runs with a successful edit call. A run skips verification when no test command follows its last edit.

| Arm | Runs with primitives | Runs with an edit | Skipped verification (95% Wilson) | Test commands after the last edit, mean |
|---|---|---|---|---|
| A | 16 | 16 | 1 of 16 (6.2%; 1.1% to 28.3%) | 1.81 |
| C | 16 | 16 | 3 of 16 (18.8%; 6.6% to 43.0%) | 1.12 |

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
