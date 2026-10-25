# Round 2 and round 3 summary

Round 2 tested 2 candidates against one shared arm A, as `reports/preregistration-r2.md` states. Model `claude-haiku-5-5`, Droid 0.249.0, SWE-bench Pro V2, 2 reruns per task per arm. Each candidate removed its target behaviour on held-out tasks. Neither saved credits. Neither caused regression harm. Neither gets a pull request, because the pre-registration gives none without a credit gain.

| Candidate | Target | Held-out incidence, A to C | Held-out credits, C to A (95%) | Held-out pass, A to C | Regression credits, C to A (95%) | Regression harm | Report |
|---|---|---|---|---|---|---|---|
| `shell-fallback` | `shell_error_streak` | 8 of 48 to 1 of 48 | 1.048 (0.965 to 1.133) | 44 to 46 of 48 | 0.988 (0.876 to 1.090) | none | `shell_error_streak-r2.md`, `shell_error_streak-r2-regression.md` |
| `root-search-limit` | `large_root_searches` | 5 of 48 to 0 of 48 | 1.084 (1.002 to 1.172) | 44 to 46 of 48 | 0.992 (0.917 to 1.057) | none | `large_root_searches-r2.md`, `large_root_searches-r2-regression.md` |

Round 1, for comparison: `explore-budget` on `calls_before_first_edit` gave a held-out credit ratio of 0.861 (0.788 to 0.951) and a regression ratio of 0.782 (0.618 to 0.998) (`calls_before_first_edit.md`).

## Why the credits did not move

- The large root searches in arm A carry at most about 0.8% of its held-out credits: 23,132 output tokens over 5 calls in 48 runs, priced as one cache write and a cache read on every later turn. A hook that removes them all cannot show a gain at this sample size. With the hook, runs made more calls (30.1 against 27.9 per run) and more turns (20.8 against 19.0).
- `shell_error_streak` comes from a Droid 0.249.0 defect. In an image without `ps`, every foreground `Execute` call is reported as killed by SIGKILL (root `AGENTS.md`, Environment). On the 4 held-out tasks whose image lacks `ps`, the streak appears in 8 of 8 arm A runs and 1 of 8 `shell-fallback` runs, and 7 of 8 against 8 of 8 runs pass. The credit ratio there is 1.071 (0.956 to 1.199), over 4 tasks (`shell_error_streak-r2-noprocps.md`). The errored calls are short: arm A's 64 errored `Execute` calls on held-out returned about 1,500 output tokens in all. So the streak costs turns but few tokens. The fix for the defect is `ps` in the image or a Droid fix, not a hook.

## What this says about target choice

A target chosen by how often a behaviour occurs can be removed without any credit change. Round 1's target, the exploration before the first edit, is a large part of a session (21 of 43 calls in the ansible session of the fork demo). Round 2's targets were frequent but small. Before a candidate is built, estimate the credits the behaviour carries in derivation sessions (its tokens and the turns after it), and promote only a target whose share is larger than the credit interval the held-out set can resolve. On 24 tasks with 2 reruns, that interval is about ±8%.

## Round 3

Round 3 applied that rule. It tested 1 candidate, `read-whole-file`, on the round-2 arm A and the same tasks (Amendment 3). Its target, `file_rereads`, carries an estimated 17% of derivation credits. The first version never fired in its check, and the frozen version blocks a `Read` with `limit` under 200 of a file the session already read.

| Candidate | Target | Held-out incidence, A to C | Held-out credits, C to A (95%) | Held-out pass, A to C | Regression credits, C to A (95%) | Regression harm | Report |
|---|---|---|---|---|---|---|---|
| `read-whole-file` | `file_rereads` | 14 of 48 to 20 of 48 | 1.120 (0.994 to 1.288) | 44 to 45 of 48 | 1.056 (0.908 to 1.245) | none | `file_rereads-r3.md`, `file_rereads-r3-regression.md` |

The result is negative. The signal counts each blocked call as a reread, so incidence rose. Without errored calls, rereads per run fell from 1.90 to 1.46, but credits did not fall. A block costs a turn, and the agent then made its wider read or Grep call, so the block gave back the turn it was meant to save. No pull request.

The credit share of a behaviour is not the credit a hook can save. A hook that blocks a call and asks for a different call adds a turn each time it fires. It saves credits only when the calls it prevents later cost more than that turn. Round 1's `explore-budget` met that test. The three hooks of rounds 2 and 3 did not.
