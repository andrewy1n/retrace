# Retrace dashboard

An [Evidence](https://evidence.dev) project. Each page is a Markdown file with SQL blocks. The data comes from Tiger through the read-only role `retrace_dashboard`. The dashboard has a light theme only.

| Page | File | Data |
|---|---|---|
| Proposals (home) | `pages/index.md` | Example: `sources/mock/proposals.csv`. Cards sorted with "in review" first. Each card has the targeted-behaviour and credit differences with intervals, the guard proxies, and a link to the pull request. |
| Proposal | `pages/proposals/[proposal_id].md` | Example proposal row. Tabs: Overview (overlay files, diff, rollback), Evidence (intervals, and for a cost proposal two real `pro-baseline1` sessions), Replay, shown as "Pipeline check" for the example proposal (real step strip of one ansible session, and the proxies of its test forks read from Tiger, so it shows that forks run, not that a change works). |
| Runs | `pages/runs.md` | Real: per job and arm, trials, credits (mean and median), assistant turns, test behaviour from primitives (test runs, whole-suite runs, long test runs), timeouts, and the proxies. Then the proxies and credits of checkpoint forks. |
| Sessions | `pages/sessions/index.md` | Real: `primitives_sessions` joined to `replay_runs`, with test behaviour from `primitives_calls`. Job filter, sortable table, one detail page per session (`pages/sessions/[session_id].md`). |
| Monitoring | `pages/monitoring.md` | Example: `sources/mock/monitoring.csv`. Daily series for a shipped change, with the ship date marked: behaviour incidence, credits, and repo-test regressions per session, before against after. Rollback is a pull request revert. |

The dashboard shows no grader data. The dashboard role reads the view `replay_runs`, which has no `passed` or `grader` column, plus `primitives_sessions` and `primitives_calls`. It cannot read `replay_results`. Grader results live in `reports/`.

The top bar (`pages/+layout.svelte`) links Proposals, Runs, Sessions, and Monitoring. Shared UI is in `components/`. `format.js` holds the status names, the verdict rule, and the interval chart.

The mock columns follow `analysis/proposals/<id>/proposal.json` (`proposal_id`, `failure_type`, `change_type`, `pr_url`) plus the Tiger summary fields. Checkpoint forks show as "Diagnosis only", with proxy counts and no interval. The page never reads review decisions from `runs/reviews/` yet. The `review_decision` column is a mock until a source exists.

Labeled "example data" on a page means a mockup until Kate's proposals and diagnoses exist.

## Run

```bash
cd dashboard
npm install            # Node 18 or later; tested on Node 24
./run.sh sources       # pulls data from Tiger into .evidence/ (about 10 s, not committed)
./run.sh dev           # http://localhost:3100, hot reload
./run.sh live          # dev plus a data refresh every 30 s (REFRESH=seconds); reload the browser to see new rows
./run.sh build && ./run.sh preview   # static site without the dev query boxes
```

`run.sh` reads `TIGER_DASHBOARD_URL` from the repo `.env` and passes it to Evidence as `EVIDENCE_SOURCE__tiger__*` variables. No credential goes into a file. Evidence reads a snapshot, not the live database. Run `sources` again, or use `live`, to refresh the data. An open page shows new data only after a browser reload (tested 2026-10-24).

## Notes

- Versions are pinned in `package.json`. The current `degit evidence-dev/template` gives the hosted Evidence Studio template, not this one.
- Do not put a backslash or `{n}` in the SQL of a page. Evidence reads it as a JavaScript template and the page fails with a 500 error.
- Evidence reads a fence it does not know, such as `diff`, as a SQL query. The diff view uses `diff2html` instead.
- A change to `evidence.config.yaml` needs a restart.
- The diff view ignores Evidence's dark theme, which is one reason the theme is light only.
- The layout hides the query boxes on every load. Remove the `onMount` line in `pages/+layout.svelte` to show them in dev.
- `@evidence-dev/csv` reads `sources/mock/`. It must stay in `evidence.config.yaml` under `datasources`.
