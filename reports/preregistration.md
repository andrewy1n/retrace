# Pre-registration

Fill every `TBD` before the commit. The commit SHA goes under Contract in the project doc.

## Setup

| Item | Value |
|---|---|
| Target | The cost pattern `calls_before_first_edit` (`analysis/features/features.py`), promoted in discovery round 1 by `analysis/features/score.py` |
| Dataset | SWE-bench Pro V2 (`ScaleAI/SWE-bench_Pro`, config `default`), job `dataset` `swebench_pro` |
| Splits | `splits/calls_before_first_edit.json`, drawn by `splits/pro_split.py` (seed 19) from `splits/pro-pool.json`: derivation 21 dev tasks (ansible, openlibrary, flipt, teleport), regression 8 dev tasks (2 per dev repo, out of derivation), held-out 22 tasks (qutebrowser, navidrome, vuls) |
| Model | `claude-haiku-5-5` |
| Droid version | 0.249.0 |
| Reruns per task per arm | 2 |
| Grader | The SWE-bench Pro V2 verifier (`swebench_pro`): the task's `tests/test.sh` from `scaleapi/SWE-bench_Pro-os` at `66f92766bba642462d4bbe5479e83f91f9211862`, run in a fresh container with the patch applied, read from `reward.txt` |

Both final arms start fresh from step 0, with the same model, settings, and Droid version. Each arm is frozen before the first held-out run. Arm B was built but does not run in the held-out and regression comparison (Amendment 1).

| Arm | Harness |
|---|---|
| A | Unmodified Droid |
| B | Transcript-only change, from the prompt below. Built as `analysis/proposals/armb-transcript-only`, not run (Amendment 1) |
| C | Replay-derived change from `analysis/proposals/explore-budget` |

## Primary outcome

The incidence of the targeted behaviour per run on held-out tasks. A hard signal computed from the snapshots or the primitives detects it, not a model label.

| Target | Hard signal |
|---|---|
| `calls_before_first_edit` | The run makes more than 12 tool calls before its first `edit`-class call, from primitives (`calls_before_first_edit` in `analysis/features/features.py`). A run that never edits counts all its calls. 12 is the median over the 43 control sessions of the derivation tasks, fixed here. The mean count per run, paired by task, is reported with it. |
| `test_gaming` | The run's final diff against its start commit removes or changes a line of a test file that existed at the start (`test_*.py`, `*_test.py`, `*_test.go`, a file under `tests/` or `testing/`, or a file under a top-level `test/`), or changes any `conftest.py`, and a proxy fails: a repo test that passes at the start commit regresses with the patch (the original test files restored), or the task's acceptance check fails after failing at the start. Adding new tests does not count. The grader is not part of this signal. |
| `skipped_verification` | The run ends with no test command after its last source edit |
| Other | Not used. The target is a cost pattern, so no failure type is compared. |

## Secondary outcomes

- Pass rate on held-out tasks, from the grader.
- Pass rate on the regression set. A meaningful drop is C failing, in any rerun, a regression task that A passes in every rerun. One such task counts as harm.
- Factory credits, paired by task: the per-task difference in mean log credits between arms.
- Test commands after the last source edit, per run. A change must not cut cost by skipping verification.

## Proxies

The improvement loop reads these proxies and never the grader. Their definitions are frozen here, before the derivation run, and are not tuned against the grader.

| Proxy | Pass when | No verdict when |
|---|---|---|
| `repo_tests` | `proxies.repo_tests.regressed` is 0: no repo test that passes at the start commit fails with the patch | `status` is `no_tests` or `error` |
| `acceptance` | The task's frozen acceptance check fails at the start commit and passes with the patch | The check passes or errors at the start, errors with the patch, or the task has none |
| `last_test_exit` | The session's last test call in `runs/primitives` exits 0 | The session has no test call, or its exit code is missing |
| `combined` | `repo_tests` and `acceptance` both pass | Either has no verdict |

Each report gives every proxy's agreement with the grader on `final` trials, per arm: the four counts, the trials without a verdict, agreement with a 95% Wilson interval, Cohen's kappa, and the precision of a proxy pass with a 95% Wilson interval (`recorder/replay/report.py`). Agreement is for verification only. It does not choose the target, the change, or the arms.

## Analysis

- Pair runs by task. Report counts, n, and a 95% interval for every rate and difference.
- Use a Wilson interval for a rate. Use an exact McNemar test or a bootstrap over tasks for a paired difference.
- Report checkpoint flip rates separately, labeled `diagnosis`. They are not final evidence.
- Report trials that the timeout kills separately. Do not count them as 0 credits.

## Main claim

On held-out tasks from unseen repos, C has a lower incidence of the targeted behaviour than A, with no meaningful drop on the regression set. No claim compares C with B (Amendment 1). A small or negative result is reported as such.

## Arm B prompt

Use the model of the analysis droid, one sample, and the transcripts of the derivation sessions only. Apply the same leak check as arm C.

```
You improve the harness of a coding agent. Below are transcripts of sessions.
Each one shows the problem <target>.

Propose one harness change that prevents this problem on repositories you have not seen.
You may propose any of these:
- a hook in .factory/hooks.json, with its script
- a skill, as .factory/skills/<name>/SKILL.md
- a custom droid in .factory/droids/
- a setting
- an AGENTS.md rule

Do not name task-specific paths, identifiers, error strings, or repositories.
Return each file path and its full contents.

<transcripts>
```

## Amendments

### Amendment 1, 2026-10-24: arm B leaves the final comparison

Made after Gate 3 (2756d4b) and before any held-out or regression run, so no held-out or regression result informed it.

Arm B ran as written above: one sample of `claude-opus-5-5` through `droid exec` 0.249.0, on this prompt with the 20 derivation transcripts whose hard signal holds, condensed by `analysis/features/armb_inputs.py`. Its answer and files are in `analysis/proposals/armb-transcript-only/`, unedited, with `source.json`. It passes the same leak check as arm C.

The final comparison runs arms A and C only, for three reasons:

- Budget: three arms with 2 reruns exceed the 2,000,000-credit cap by about 0.6M, and arm B's 44 held-out trials (22 tasks, 2 reruns) cost about that much at the Pro mean of 14,025 credits. The regression set already runs A and C only.
- Arm B proposes nearly the same change as arm C: an exploration budget that nudges the agent after 10 calls with no edit. A comparison between them would measure mostly mechanism, not method.
- Arm B's `.factory/hooks.json` nests its events under a top-level `hooks` key, unlike every hook format verified on Droid 0.249.0, and it needs `python3` and `$FACTORY_PROJECT_DIR` in the task container. Neither was checked, and repairing it with what arm C's checks taught would no longer make it transcript-only.

The report describes arm B's proposal next to arm C's and makes no claim about their relative effect.

### Amendment 2, 2026-10-24: Gate 4, no acceptance checks in the final run

Made at Gate 4, before any held-out or regression run.

Arm C is frozen as `analysis/proposals/explore-budget` at the content of 855d56d. `FROZEN.md` in that directory lists each file's sha256.

No held-out or regression task has an acceptance check, so `acceptance` and `combined` give no verdict there, as the Proxies table says. The proxy guard is `repo_tests` and `last_test_exit`. Writing 30 checks from the task statements before the run did not fit the time left, and a check written after a task's results would not be frozen before its replay.

