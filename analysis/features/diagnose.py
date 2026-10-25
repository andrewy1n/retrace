"""Diagnose the target's sessions: which calls make up the exploration before the first edit.

  python analysis/features/diagnose.py [--splits splits/<group>.json] [--out runs/diagnoses]

For each control step0 session of a derivation task whose hard signal holds (more than
THRESHOLD calls before the first edit, reports/preregistration.md), writes
runs/diagnoses/<session-id>.json: the cited tool_call_ids, the kinds of call among them,
and the pattern they fit. summary.json lists the counts and what stays unexplained: the
costliest derivation sessions without the signal. Reads primitives and jobs only.
"""

import argparse
import json
import statistics
from pathlib import Path

from features import calls_before_first_edit

ROOT = Path(__file__).resolve().parents[2]
TARGET = "calls_before_first_edit"
THRESHOLD = 12  # the pre-registered hard signal

PATTERNS = {
    "rereads": "re-opens files it has already read, often in chunks, before deciding on a change",
    "searches": "searches the repo repeatedly before opening the code it changes",
    "broad_reads": "reads many distinct files before the first edit",
    "runs_first": "runs code or tests before the first edit",
    "mixed": "spreads exploration across reads and searches with no single dominant kind",
}


def pattern(counts):
    if counts["reads"] and counts["rereads"] >= counts["reads"] / 3:
        return "rereads"
    if counts["searches"] >= counts["calls"] / 3:
        return "searches"
    if counts["distinct_files_read"] >= 8:
        return "broad_reads"
    if counts["runs"]:
        return "runs_first"
    return "mixed"


def diagnose(p):
    calls = p["calls"]
    n = calls_before_first_edit(calls)
    before = calls[:n]
    seen, rereads = set(), 0
    for c in before:
        if c["command_class"] == "read" and c["files"]:
            rereads += all(f in seen for f in c["files"])
            seen.update(c["files"])
    counts = {
        "calls": n,
        "reads": sum(c["command_class"] == "read" for c in before),
        "rereads": rereads,
        "distinct_files_read": len(seen),
        "searches": sum(c["command_class"] == "search" for c in before),
        "runs": sum(c["command_class"] in ("run", "test") for c in before),
        "output_tokens_est": sum(c["output_tokens_est"] or 0 for c in before),
    }
    kind = pattern(counts)
    return {
        "session_id": p["session_id"],
        "task_id": p["task_id"],
        "target": TARGET,
        "value": n,
        "first_edit_tool_call_id": calls[n]["tool_call_id"] if n < len(calls) else None,
        "cited_tool_call_ids": [c["tool_call_id"] for c in before],
        "counts": counts,
        "pattern": kind,
        "explanation": f"The session makes {n} calls before its first edit: it {PATTERNS[kind]}.",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--splits", type=Path, default=ROOT / "splits" / f"{TARGET}.json")
    ap.add_argument("--primitives", type=Path, default=ROOT / "runs" / "primitives")
    ap.add_argument("--jobs", type=Path, default=ROOT / "runs" / "jobs")
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "diagnoses")
    args = ap.parse_args()

    derivation = set(json.loads(args.splits.read_text())["derivation"])
    sessions = []
    for path in sorted(args.primitives.glob("*.json")):
        p = json.loads(path.read_text())
        job = json.loads((args.jobs / f"{p['job_id']}.json").read_text())
        if p["task_id"] in derivation and job.get("start") == "step0" and job["arm"]["kind"] == "control":
            sessions.append(p)

    args.out.mkdir(parents=True, exist_ok=True)
    diagnosed = [diagnose(p) for p in sessions if calls_before_first_edit(p["calls"]) > THRESHOLD]
    for d in diagnosed:
        (args.out / f"{d['session_id']}.json").write_text(json.dumps(d, indent=2) + "\n", newline="\n")

    credits = {p["session_id"]: p["token_usage"]["factory_credits"] for p in sessions}
    cutoff = statistics.quantiles(credits.values(), n=4)[2]
    hit = {d["session_id"] for d in diagnosed}
    summary = {
        "target": TARGET,
        "threshold": THRESHOLD,
        "sessions": len(sessions),
        "with_signal": len(diagnosed),
        "patterns": {k: sum(d["pattern"] == k for d in diagnosed) for k in PATTERNS},
        "unexplained": sorted(s for s, c in credits.items() if c >= cutoff and s not in hit),
        "unexplained_rule": "costliest quarter of derivation sessions (factory_credits) without the signal",
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", newline="\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "unexplained"}, indent=2))
    print(f"unexplained: {len(summary['unexplained'])} of the costliest quarter")


if __name__ == "__main__":
    main()
