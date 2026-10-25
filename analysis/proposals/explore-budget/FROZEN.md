Arm C for the `calls_before_first_edit` target, frozen at Gate 4 on 2026-10-24. Its content is the version committed in 855d56d. Nobody edits this directory after the freeze. A revised change needs a new proposal directory and new held-out and regression tasks (the Grader section of `AGENTS.md`).

The runner copies only `.factory/` onto the task checkout. sha256 of each file at the freeze:

| File | sha256 |
|---|---|
| `.factory/hooks.json` | `65e5b706558a978ea66deb00019f5ab0c9bd76ce5a7c797df022fa73dd452e6f` |
| `.factory/hooks/explore_budget.sh` | `434362ece538759eb050d1222755f2eb8477e314aa08da53868f3ac63817a415` |
| `proposal.json` (with `pr_url`) | `f53b3e6a7ad6644e2a50f14d336af4253e0ad3ac75a96f85d3fbb6c8b3ce3735` |
| `test_hook.sh` | `0d4776b5a43555c470b11e49f4f8c6bc3535956d6eb4db36058e1cf2461c8e9d` |

Before the freeze it ran in Droid 0.249.0 on two derivation tasks (`pro-explore-check1`, 855d56d's results). Its message reached the model. That run used the version before the parallel-call fix, and the fixed version has run only in `test_hook.sh`.
