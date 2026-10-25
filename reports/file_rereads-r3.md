# file_rereads-r3

Evidence: step-0 `final` results.

## Setup

- Model: claude-haiku-5-5. Droid: 0.249.0. Grader: swebench_pro.
- Arms: A = r2-heldout-a; C = r3-heldout-read-whole-file.
- Checkout (`repo_sha`): 6f9ba338e9de, bb9cfee3e881, c6892adbd519.
- Control: A. Trials killed by the timeout are counted apart and left out of credits.

## Arms

| Arm | Tasks | Trials | Passed | Pass rate (95% Wilson) | Timed out | Credits | Credits per trial | file_rereads runs |
|---|---|---|---|---|---|---|---|---|
| A | 24 | 48 | 44 | 91.7% (80.4% to 96.7%) | 1 | 384,056 | 8,171 | 14 of 48 (29.2%; 18.2% to 43.2%) |
| C | 24 | 48 | 45 | 93.8% (83.2% to 97.9%) | 2 | 372,336 | 8,094 | 20 of 48 (41.7%; 28.8% to 55.7%) |

## Paired differences

### C against A

Tasks in both arms: 24. Left out: 0.

- Pass rate difference (C minus A): +2.1 points (95% interval +0.0 to +6.2).
- Tasks where only A passes every rerun: 0. Only C: 0. Exact McNemar p = 1.000.
- Credits, geometric-mean ratio C to A: 1.120 (95% interval 0.994 to 1.288) over 23 tasks.
- file_rereads incidence difference (C minus A), share of a task's runs, over 24 tasks with primitives in both arms: +12.5 points (95% interval +0.0 to +27.1).
- Tasks where only A shows file_rereads in some run: 0. Only C: 4. Exact McNemar p = 0.125.
- Mean file_rereads count difference (C minus A), paired by task, over 24 tasks: +0.5 calls (95% interval -0.0 to +1.0).

## Verification after the last edit

Runs with a successful edit call. A run skips verification when no test command follows its last edit.

| Arm | Runs with primitives | Runs with an edit | Skipped verification (95% Wilson) | Test commands after the last edit, mean |
|---|---|---|---|---|
| A | 48 | 48 | 3 of 48 (6.2%; 2.1% to 16.8%) | 1.90 |
| C | 48 | 48 | 2 of 48 (4.2%; 1.2% to 14.0%) | 1.94 |

## Proxy agreement

Agreement with the dataset grader on final trials. For verification only; the improvement loop never reads it.

| Arm | Proxy | Usable | Excluded | Proxy pass, grader pass | Proxy pass, grader fail | Proxy fail, grader pass | Proxy fail, grader fail | Agreement (95% Wilson) | Kappa | Precision of proxy pass (95% Wilson) |
|---|---|---|---|---|---|---|---|---|---|---|
| A | repo_tests | 37 | 11 | 20 | 1 | 14 | 2 | 59.5% (43.5% to 73.7%) | 0.09 | 95.2% (77.3% to 99.2%) |
| A | acceptance | 0 | 48 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| A | last_test_exit | 38 | 10 | 35 | 3 | 0 | 0 | 92.1% (79.2% to 97.3%) | 0.00 | 92.1% (79.2% to 97.3%) |
| A | combined | 0 | 48 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| C | repo_tests | 36 | 12 | 19 | 1 | 15 | 1 | 55.6% (39.6% to 70.5%) | 0.01 | 95.0% (76.4% to 99.1%) |
| C | acceptance | 0 | 48 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| C | last_test_exit | 38 | 10 | 36 | 2 | 0 | 0 | 94.7% (82.7% to 98.5%) | 0.00 | 94.7% (82.7% to 98.5%) |
| C | combined | 0 | 48 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| all | repo_tests | 73 | 23 | 39 | 2 | 29 | 3 | 57.5% (46.1% to 68.2%) | 0.05 | 95.1% (83.9% to 98.7%) |
| all | acceptance | 0 | 96 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |
| all | last_test_exit | 76 | 20 | 71 | 5 | 0 | 0 | 93.4% (85.5% to 97.2%) | 0.00 | 93.4% (85.5% to 97.2%) |
| all | combined | 0 | 96 | 0 | 0 | 0 | 0 | n/a (n/a to n/a) | n/a | n/a (n/a to n/a) |

## Round 3 context

- Round 3 tested 1 candidate, `read-whole-file`, against the round-2 arm A (`reports/preregistration-r2.md`, Amendment 3).
- Time gap. Arm A trials finished between 08:00 and 09:36 UTC on 2026-10-25. Arm C trials finished between 11:15 and 12:00 UTC, so about 2 to 4 hours after arm A. Both arms used the same model, Droid version, settings, and worker.
- The signal counts every `Read` call, including the calls the hook blocks. 44 of arm C's `Read` calls are errors, against 3 in arm A, and each blocked call is a reread by the signal's rule. Without errored calls, rereads per run are 1.90 in arm A and 1.46 in arm C. This breakdown was not pre-registered.
