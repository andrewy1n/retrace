# Retrace dashboard

An [Evidence](https://evidence.dev) project. Each page is a Markdown file with SQL blocks. The data comes from Tiger through the read-only role `retrace_dashboard`. The dashboard has a light theme only.

| Page | File | Data |
|---|---|---|
| Proposals (home) | `pages/index.md` | Real when `analysis/proposals/` has a `proposal.json`, else the example rows in `sources/mock/proposals.csv`. Cards sorted with "in review" first. Each card has the targeted-behaviour and credit differences with intervals, the guard proxies, and a link to the pull request. See "Proposal cards". |
| Proposal | `pages/proposals/[proposal_id].md` | Example proposal row. Tabs: Overview (overlay files, diff, rollback), Evidence (intervals, and for a cost proposal two real `pro-baseline1` sessions), Replay, shown as "Pipeline check" for the example proposal (real step strip of one ansible session, and the proxies of its test forks read from Tiger, so it shows that forks run, not that a change works). |
| Runs | `pages/runs.md` | Real: `primitives_sessions` and `primitives_calls` joined to `replay_runs`, with a job filter. Charts: cumulative credit share, credits against turns, mean credits per job and arm, tool output and time by command class, test runs per session, long test runs, and the proxies of step-0 runs. Then the session table and the checkpoint forks. Each session links to `pages/sessions/[session_id].md`, which charts time and tool output per call. |
| Monitoring | `pages/monitoring.md` | Example: `sources/mock/monitoring.csv`. Daily series for a shipped change, with the ship date marked: behaviour incidence, credits, and repo-test regressions per session, before against after. Rollback is a pull request revert. |

The dashboard shows no grader data. The dashboard role reads the view `replay_runs`, which has no `passed` or `grader` column, plus `primitives_sessions` and `primitives_calls`. It cannot read `replay_results`. Grader results live in `reports/`.

The top bar (`pages/+layout.svelte`) links Proposals, Runs, and Monitoring. Chart colors are the validated categorical palette in `evidence.config.yaml`; a command class, an arm, or a proxy status keeps the same color on every page. Shared UI is in `components/`. `format.js` holds the status names, the verdict rule, and the interval chart.

The mock columns follow `analysis/proposals/<id>/proposal.json` (`proposal_id`, `failure_type`, `change_type`, `pr_url`) plus the Tiger summary fields. Checkpoint forks show as "Diagnosis only", with proxy counts and no interval. The page never reads review decisions from `runs/reviews/` yet. The `review_decision` column is a mock until a source exists.

Labeled "example data" on a page means a mockup until Kate's proposals and diagnoses exist.

## Proposal cards

`proposal_list.py` writes `sources/proposal_list/proposals.csv` (gitignored) on every `./run.sh sources`. It has one row per `analysis/proposals/<id>/proposal.json`, plus the overlay file list and its diff. With no proposal the file holds one empty row and the pages show the mock rows with an "Example data" label.

A candidate job in `runs/jobs/` names the proposal in `arm.path`. Its control job is `<name>-control` when the candidate job is `<name>-candidate`, else the one control job with the same `task_ids`. A proposal with no such pair is "Drafted" and has no numbers.

The numbers come from `sources/tiger/proposal_runs.sql`: the `final` step-0 rows of the view `replay_runs` (no `passed`, no `grader`) joined to `primitives_calls`. `components/proposals.js` computes the card in the browser, like `report.py`: paired by task, percentile bootstrap over tasks (10,000 resamples, fixed seed).

- Incidence of the target behaviour. Per run, `signal_whole_suite_tests` is true when a call has a `test_runner`, `path_arg_count` 0, and `duration_s` over 60. `signal_calls_before_first_edit` is true when the first `edit` call has `position` above 12, or the run has more than 12 calls and no edit. Both match `SIGNALS` in `recorder/replay/report.py`. A run without primitives is left out. The card shows the paired difference in percentage points with its interval, and the counts per arm. Add a signal in `SIGNALS` of `components/proposals.js` and as a column in `proposal_runs.sql`. A target with no signal shows "Not measured".
- Credits. Paired difference of mean log credits per task, shown as a percent. A run that the timeout killed is left out.
- Guards. Repo tests count runs with status `ok` that regress a test. The acceptance check counts runs that failed at the start and did not error.
- Status. A `pr_url` makes it "In review". Jobs with results and no `pr_url` make it "Replay". The rest is "Drafted". Shipped and rejected wait for `runs/reviews/`.

Set `PROPOSALS` and `JOBS` to other directories to test with a throwaway proposal.

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
- `run.sh preview` fails with `unknown or unexpected option: --port` (tested 2026-10-24). Serve `build/` with `python3 -m http.server` instead.
- Evidence writes no table for an empty CSV and keeps the old one, so `run.sh sources` deletes `.evidence/template/static/data/proposal_list` first.
- The diff view ignores Evidence's dark theme, which is one reason the theme is light only.
- The layout hides the query boxes on every load. Remove the `onMount` line in `pages/+layout.svelte` to show them in dev.
- `@evidence-dev/csv` reads `sources/mock/`. It must stay in `evidence.config.yaml` under `datasources`.
