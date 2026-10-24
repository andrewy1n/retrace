# Retrace dashboard

An [Evidence](https://evidence.dev) project. Each page is a Markdown file with SQL blocks. The data comes from Tiger through the read-only role `retrace_dashboard`. The dashboard has a light theme only.

| Page | File | Data |
|---|---|---|
| Sessions | `pages/index.md` | Real: `primitives_sessions` joined to `replay_results`. Job filter, sortable table, one detail page per session (`pages/sessions/[session_id].md`). |
| Results | `pages/results.md` | Real: pass rate with a Wilson 95% interval, credits, and timeouts per job and arm. |
| Replay | `pages/replay.md` | The step strip is real (primitives of one session). The replay matrix holds typed-in results from the 12 test forks. The decisive step is an example. |
| Proposal | `pages/proposal.md` | Example data, except the tool-call chart and the pass-rate intervals. It shows a code diff of a sample change. |

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
- The dev server shows a box for each query. A built site hides them.
