# Retrace

Replay recorded Droid sessions, and keep a harness change only when it beats a no-hint control. Factory Signals is credited for the friction-ticket ideas. Retrace tests a proposal before it ships.

Andrew owns recording, replay, and the dashboard. Kate owns the labeler, proposals, and the Tiger schema. Claude Code is an optional adapter. The GitHub repository is public. The plan and the pitch are in the [Retrace project doc](https://docs.google.com/document/d/1sAXpAyjByro-vfbUc1EXLp-weLUiXahmg3GEDRCgrrw/edit). Agent instructions are in `AGENTS.md`. The project summary is the Pitch section of the project doc.

## Layout

| Path | What it holds |
| --- | --- |
| `contracts/` | Trace, friction ticket, replay job, replay result, and proposed change schemas, plus one fixture each |
| `recorder/` | Droid capture hook and replay runner |
| `analysis/` | Labeler and `.factory/` proposal directories |
| `runs/` | Trace indexes, labels, tickets, jobs, results, and reviews |
| `splits/` | Derivation, held-out, and regression instance ids |
| `reports/` | Frozen comparisons |

`dashboard/` is added with its first page. Proposal review starts from a friction ticket and shows the `.factory/hooks.json` guardrail. The Changes tab shows a before-and-after for the target failure type against untargeted types, a shipped-changes table, and rollback. Those figures come from Tiger summaries. Pass/fail is the SWE-bench grader.

## Pitch and plan

The pitch, the order, the cut list, open questions, and unverified items are in the [project doc](https://docs.google.com/document/d/1sAXpAyjByro-vfbUc1EXLp-weLUiXahmg3GEDRCgrrw/edit). The pre-registered claim is in `reports/preregistration.md`.

`retrace-summary-v2.pdf` is superseded. Where it disagrees with this repository or the project doc, the repository wins for code and the project doc wins for the plan. The submission PDF is exported from the Pitch section.
