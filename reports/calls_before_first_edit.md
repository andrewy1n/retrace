# calls_before_first_edit

Evidence: step-0 `final` results.

## Setup

- Model: claude-haiku-5-5. Droid: 0.249.0. Grader: swebench_pro.
- Arms: A = final1-heldout-a; C = final1-heldout-c.
- Checkout (`repo_sha`): d4f304b6f4a7.
- Control: A. Trials killed by the timeout are counted apart and left out of credits.

## Arms

| Arm | Tasks | Trials | Passed | Pass rate (95% Wilson) | Timed out | Credits | Credits per trial | calls_before_first_edit runs |
|---|---|---|---|---|---|---|---|---|
| A | 22 | 44 | 43 | 97.7% (88.2% to 99.6%) | 0 | 484,322 | 11,007 | 27 of 44 (61.4%; 46.6% to 74.3%) |
| C | 22 | 44 | 44 | 100.0% (92.0% to 100.0%) | 0 | 411,629 | 9,355 | 4 of 44 (9.1%; 3.6% to 21.2%) |

## Paired differences

### C against A

Tasks in both arms: 22. Left out: 0.

- Pass rate difference (C minus A): +2.3 points (95% interval +0.0 to +6.8).
- Tasks where only A passes every rerun: 0. Only C: 1. Exact McNemar p = 1.000.
- Credits, geometric-mean ratio C to A: 0.861 (95% interval 0.788 to 0.951) over 22 tasks.
- calls_before_first_edit incidence difference (C minus A), share of a task's runs, over 22 tasks with primitives in both arms: -52.3 points (95% interval -65.9 to -38.6).
- Tasks where only A shows calls_before_first_edit in some run: 13. Only C: 0. Exact McNemar p = 0.000.
- Mean calls_before_first_edit count difference (C minus A), paired by task, over 22 tasks: -4.1 calls (95% interval -5.5 to -2.7).

## Verification after the last edit

Runs with a successful edit call. A run skips verification when no test command follows its last edit.

| Arm | Runs with primitives | Runs with an edit | Skipped verification (95% Wilson) | Test commands after the last edit, mean |
|---|---|---|---|---|
| A | 44 | 44 | 5 of 44 (11.4%; 5.0% to 24.0%) | 1.57 |
| C | 44 | 44 | 3 of 44 (6.8%; 2.3% to 18.2%) | 1.70 |

## Proxy agreement

Agreement with the dataset grader on final trials. For verification only; the improvement loop never reads it.

| Arm | Proxy | Usable | Excluded | Proxy pass, grader pass | Proxy pass, grader fail | Proxy fail, grader pass | Proxy fail, grader fail | Agreement (95% Wilson) | Kappa | Precision of proxy pass (95% Wilson) |
|---|---|---|---|---|---|---|---|---|---|---|
| A | repo_tests | 32 | 12 | 12 | 0 | 19 | 1 | 40.6% (25.5% to 57.7%) | 0.04 | 100.0% (75.7% to 100.0%) |
| A | acceptance | 0 | 44 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| A | last_test_exit | 34 | 10 | 33 | 1 | 0 | 0 | 97.1% (85.1% to 99.5%) | 0.00 | 97.1% (85.1% to 99.5%) |
| A | combined | 0 | 44 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| C | repo_tests | 32 | 12 | 12 | 0 | 20 | 0 | 37.5% (22.9% to 54.7%) | 0.00 | 100.0% (75.7% to 100.0%) |
| C | acceptance | 0 | 44 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| C | last_test_exit | 34 | 10 | 34 | 0 | 0 | 0 | 100.0% (89.8% to 100.0%) | n/a | 100.0% (89.8% to 100.0%) |
| C | combined | 0 | 44 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| all | repo_tests | 64 | 24 | 24 | 0 | 39 | 1 | 39.1% (28.1% to 51.3%) | 0.02 | 100.0% (86.2% to 100.0%) |
| all | acceptance | 0 | 88 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| all | last_test_exit | 68 | 20 | 67 | 1 | 0 | 0 | 98.5% (92.1% to 99.7%) | 0.00 | 98.5% (92.1% to 99.7%) |
| all | combined | 0 | 88 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
