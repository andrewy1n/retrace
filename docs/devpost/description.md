![Retrace](https://raw.githubusercontent.com/andrewy1n/retrace/4e1ad609afe0586601642fdc3633a30c91eaf780/docs/devpost/logo-banner.png)

## Inspiration

Coding agents repeat the same mistakes, and every wasted step costs tokens. The usual way to improve an agent from its traces is to ask an LLM what went wrong and what to change. Research shows that this judgment is weak at both ends. On failure logs from LLM multi-agent systems, the best method found the decisive failing step only 14.2% of the time [1]. A common fix, a repository context file such as `AGENTS.md`, did not generally improve task success and raised inference cost by over 20% [2]. The authors of that study say such changes should be rigorously evaluated before deployment.

Published systems that do evaluate their changes, such as DSPy [3], GEPA [4], the Darwin Gödel Machine [5], and Arize Prompt Learning [6], score each candidate inside the loop with a task metric or benchmark tests. A real team has no hidden test suite for its own sessions, so that loop cannot run there. A loop that selects on the grader can also overfit to it.

We wanted a loop that runs on evidence a production system already has. A trace is more than a story for an LLM to read. It is a recording you can measure and replay. Retrace finds patterns with deterministic features and tests causes by rewinding and forking sessions. It validates each fix with the repo's own tests and replay. The benchmark grader stays outside the loop and checks only the frozen fix, once, on repos the loop never saw.

## What it does

Retrace is a system for improving coding agent harnesses. It finds where an agent fails or wastes money, proposes a harness fix, and validates the fix on repos the agent has never seen.

![How Retrace improves a harness](https://raw.githubusercontent.com/andrewy1n/retrace/23e0a963cb82e2590e6a40250933d56643b1c6eb/docs/devpost/pipeline.png)

1. **Record.** Retrace runs Factory Droid on real tasks. Every tool call gets a git snapshot of the repo.
2. **Extract primitives.** Each tool call becomes a set of deterministic facts: tool type, command class, duration, exit code, files touched, output size, position, and whether it repeats an earlier call. Primitives hold no command text and no tool output.
3. **Find features.** Features are code over primitives and snapshots. Some catch failures, such as weakened tests, skipped verification, loops, and reverted edits. Others catch waste, such as re-reads and large tool outputs. A discovery agent proposes new features from the sessions that current features do not explain. Code promotes a feature only if it predicts cost on tasks it was not fit on.
4. **Diagnose.** An agent explains the expensive sessions from the promoted features and cites the exact tool calls. It also proposes new features, which code scores before keeping them.
5. **Propose.** An agent drafts the fix as a small overlay under `.factory/`: a guardrail hook, a skill, a custom droid, a setting, or an `AGENTS.md` rule, ranked in that order. It tests each draft with replay, a tool it can call.
   - **Replay (tool).** Retrace rewinds a recorded session to any tool call, restores the repo snapshot, and forks the session with the draft installed. This is a quick check of whether a cited step causes the cost. It is diagnosis, not final evidence.
6. **Validate.** The fix is frozen, and the claim is pre-registered in git. Then the fix runs fresh from step 0 against unmodified Droid. It runs on held-out tasks from unseen repos and on a regression set. Every result reports counts, sample size, and an interval.

![Replay: rewind a session and fork it](https://raw.githubusercontent.com/andrewy1n/retrace/a210e03d2898cd2a2b1538ef3ffebb55a7c22aa5/docs/devpost/replay.png)

![Retrace architecture](https://raw.githubusercontent.com/andrewy1n/retrace/23e0a963cb82e2590e6a40250933d56643b1c6eb/docs/devpost/architecture.png)

A person reviews the evidence and decides whether to adopt the fix. The dashboard lists each proposal with its effect on the targeted behaviour, the credit change, and a guard from the repo's own tests.

### The rule that keeps it honest

The improvement loop never sees the benchmark grader. A production system has no hidden test suite, so Retrace finds, diagnoses, and selects fixes with signals a real team has: traces, primitives, snapshots, and the repo's own tests. The grader scores only the frozen fix, and only people read that score. The database enforces this rule: the dashboard's role cannot read the pass/fail columns.

## The lead case: calls before the first edit

We started out hunting failures, and we found almost none. On SWE-bench Verified, Claude Haiku in Droid passed 65 of 78 trials. On SWE-bench Pro, it passed 57 of 58 dev trials. The money was a bigger problem than the failures: an average Pro trial costs about 14,000 Factory credits.

We fit Factory credits against token counts. The fit is exact over 80 sessions. Cost follows the number of turns, not wall time. A 23-minute test run costs little unless its output is large.

The discovery round promoted one feature: **calls before the first edit**. It explains 16% of within-task credit variance on tasks it was not fit on, and it holds in 3 of 4 repos. 20 of 43 derivation sessions make more than 12 tool calls before their first edit. In 14 of them, the agent pages through files it already read.

![The agent explores too long before it edits](https://raw.githubusercontent.com/andrewy1n/retrace/a210e03d2898cd2a2b1538ef3ffebb55a7c22aa5/docs/devpost/histogram.png)

The fix is a 51-line POSIX shell hook. After 10 tool calls with no edit, it blocks one call and asks the agent to make its first edit. It fires at most once per session.

We also asked an LLM to propose a fix from the same transcripts alone. It proposed nearly the same exploration budget. A comparison between the two would measure mechanism, not method, so we removed that arm from the final run and recorded the change in the pre-registration before any held-out run.

The final test runs the frozen hook against unmodified Droid on 22 held-out tasks from 3 unseen repos (qutebrowser, navidrome, vuls) and on 8 regression tasks, with 2 runs per task per arm.

**Results.** On the held-out repos, the hook cut runs with more than 12 calls before the first edit from 27 of 44 to 4 of 44: a paired difference of -52.3 points (95% CI -65.9 to -38.6). It cut credits by about 14% (geometric-mean ratio 0.861, 95% CI 0.788 to 0.951). The agent made its first edit 4.1 calls sooner on average. Pass rate did not drop: 43 of 44 runs passed without the hook, and 44 of 44 with it. On the 8 regression tasks, the behaviour fell from 9 of 16 runs to 0 of 16, and no task that passed before failed with the hook. The pass rates sit near the ceiling, so this run cannot show a pass-rate gain. One proxy, the repo's own tests, turned out weak on the held-out repos, and we report that too.

![Results: the hook cut early exploration and cost](https://raw.githubusercontent.com/andrewy1n/retrace/a210e03d2898cd2a2b1538ef3ffebb55a7c22aa5/docs/devpost/results.png)

## How we built it

- **Factory Droid CLI 0.249.0** runs every trial. The **Droid SDK** (`resumeSession` and `session.rewind`) forks a recorded session at any step. A Droid hook snapshots the repo after every tool call.
- **SWE-bench Pro V2** from Scale is the benchmark, on its Python and Go repos. We ported Scale's harness and checked that the gold patch passes and an empty patch fails on all 56 candidate tasks.
- **Vultr** hosts an x86 worker that runs 8 trials in parallel and grades them.
- **Tiger Data** (Postgres) stores primitives, features, and replay outcomes, with separate roles for the worker, the analysis, and the dashboard.
- **Evidence** builds the dashboard: Proposals, Runs, and Monitoring.
- **Python** computes the statistics: Wilson intervals, paired bootstrap, and McNemar tests.
- **Claude Code** helped us build the system and ran the feature discovery round.

## Challenges we ran into

- **Our target disappeared twice.** First, the agent passed nearly every task, so we moved from failures to cost. Next, whole-suite test runs drove waste on SWE-bench Verified but showed up in only 4 of 60 Pro sessions. We let the data choose the next target.
- **Budget.** Pro trials cost about 3 times as much as Verified trials. One job overran its credit cap, because the runner counted only finished trials. Replay forks are not cheap either. An early fork costs about as much as a full trial.
- **Environment.** Three Pro images use Alpine Linux, where the Droid binary does not start. The benchmark images are x86 only, and our laptop is arm64. In each image, the repo HEAD differs from the dataset's base commit by file mode on every file, which broke our first diffs.
- **Parallel tool calls.** Our first hook blocked every call in a parallel batch. We fixed it to block once per batch before the freeze.

## Accomplishments that we're proud of

- The grader stays out of the loop, and the database enforces it.
- The claim, metrics, splits, and proxy definitions were committed before the derivation run. The fix was frozen with a sha256 for each file.
- Rewind and fork work on a real Pro task, and the forked run passed the Pro verifier.
- An exact model of Factory credits from token counts. Output tokens are 44% of the cost.
- Thousands of real tool calls stored as primitives, with no code or transcript text leaving the machine.

## What we learned

- On these benchmarks, a small model passes nearly everything. Cost is where a harness change helps most.
- An LLM reading transcripts can propose a plausible fix. Only a controlled run on unseen tasks shows whether the fix works.
- Pre-registration is cheap, and it stops us from fooling ourselves.

## What's next for Retrace

- Measure how well the production proxies agree with the grader, and report that agreement with an interval.
- Write acceptance checks from task statements for held-out tasks before each run.
- Run more discovery rounds on the sessions that current features do not explain.
- Run on real developer sessions, with monitoring and rollback in place of the grader.
- Add a Claude Code adapter next to Droid.

## References

1. S. Zhang et al. [Which Agent Causes Task Failures and When? On Automated Failure Attribution of LLM Multi-Agent Systems](https://arxiv.org/abs/2505.00212). ICML 2025.
2. T. Gloaguen et al. [Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?](https://arxiv.org/abs/2602.11988) ICLR 2026.
3. DSPy. [Optimizers](https://dspy.ai/learn/optimization/optimizers).
4. L. A. Agrawal et al. [GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning](https://arxiv.org/abs/2507.19457). ICLR 2026.
5. J. Zhang et al. [Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents](https://arxiv.org/abs/2505.22954). ICLR 2026.
6. Arize. [Optimizing Coding Agent Prompts for Execution](https://arize.com/docs/ax/cookbooks/prompt-learning/optimizing-coding-agent-prompts-for-execution).
