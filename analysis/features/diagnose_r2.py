"""Diagnose the discovery round 2 targets: shell_error_streak and large_root_searches.

  python analysis/features/diagnose_r2.py [--splits splits/<group>.json] [--out runs/diagnoses]

For each control step0 session of a derivation task whose hard signal holds, writes
runs/diagnoses/<target>/<session-id>.json with the cited tool_call_ids, counts, and a
pattern. Each target's summary.json lists the counts and what stays unexplained: the
costliest derivation sessions without the signal. Reads primitives and jobs only.
"""

import argparse
import json
import statistics
from pathlib import Path

from features import (LARGE_OUTPUT_TOKENS, LARGE_ROOT_SEARCHES_MIN, SHELL_ERROR_STREAK_MIN,
                      large_root_searches_signal, shell_error_streak_signal)

ROOT = Path(__file__).resolve().parents[2]
TOOL_OUTPUT_CAP = 8000

PATTERNS = {
    "shell_error_streak": {
        "background_recovery": "keeps failing in the foreground shell until it runs commands in the background and reads their logs",
        "no_recovery": "never gets a shell command through after the failures start",
    },
    "large_root_searches": {
        "capped": "prints every match in the whole repo and reaches the search tool's output cap",
        "large": "prints every match in the whole repo, over 2,000 tokens",
    },
}


def shell_diagnosis(calls):
    shell = [c for c in calls if c["tool_name"] == "Execute"]
    cited = [c for prev, c in zip(shell, shell[1:]) if c["is_error"] and prev["is_error"]]
    first = shell.index(cited[0]) - 1
    recovered = [c for c in shell[first:] if c["background"] and not c["is_error"]]
    counts = {
        "shell_calls": len(shell),
        "errored_shell_calls": sum(bool(c["is_error"]) for c in shell),
        "errors_after_an_error": len(cited),
        "fast_errors": sum(bool(c["is_error"]) and (c["duration_s"] or 0) < 1 for c in shell),
        "background_calls_after_first_error": len(recovered),
        "log_reads": sum(c["command_class"] == "read" and any(f.startswith("/tmp/") for f in c["files"]) for c in calls),
    }
    kind = "background_recovery" if recovered else "no_recovery"
    return [shell[first]] + cited, counts, kind


def search_diagnosis(calls):
    cited = [c for c in calls if c["command_class"] == "search" and c["files"] == ["."]
             and (c["output_tokens_est"] or 0) > LARGE_OUTPUT_TOKENS]
    counts = {
        "root_searches": sum(c["command_class"] == "search" and c["files"] == ["."] for c in calls),
        "large_root_searches": len(cited),
        "output_tokens_est": sum(c["output_tokens_est"] for c in cited),
        "carried_output_tokens": sum(c["output_tokens_est"] * c["turns_after"] for c in cited),
    }
    kind = "capped" if any(c["output_tokens_est"] >= TOOL_OUTPUT_CAP for c in cited) else "large"
    return cited, counts, kind


TARGETS = {
    "shell_error_streak": (shell_error_streak_signal, shell_diagnosis, SHELL_ERROR_STREAK_MIN),
    "large_root_searches": (large_root_searches_signal, search_diagnosis, LARGE_ROOT_SEARCHES_MIN),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--splits", type=Path, default=ROOT / "splits" / "calls_before_first_edit.json")
    ap.add_argument("--primitives", type=Path, default=ROOT / "runs" / "primitives")
    ap.add_argument("--jobs", type=Path, default=ROOT / "runs" / "jobs")
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "diagnoses")
    args = ap.parse_args()

    derivation = set(json.loads(args.splits.read_text())["derivation"])
    sessions = []
    for path in sorted(args.primitives.glob("*.json")):
        p = json.loads(path.read_text())
        if p["task_id"] not in derivation:
            continue
        job = json.loads((args.jobs / f"{p['job_id']}.json").read_text())
        if job.get("start") == "step0" and job["arm"]["kind"] == "control":
            sessions.append(p)
    credits = {p["session_id"]: p["token_usage"]["factory_credits"] for p in sessions}
    cutoff = statistics.quantiles(credits.values(), n=4)[2]

    for target, (signal, diagnose, threshold) in TARGETS.items():
        out = args.out / target
        out.mkdir(parents=True, exist_ok=True)
        diagnosed = []
        for p in sessions:
            holds, n = signal(p["calls"])
            if not holds:
                continue
            cited, counts, kind = diagnose(p["calls"])
            d = {
                "session_id": p["session_id"],
                "task_id": p["task_id"],
                "target": target,
                "value": n,
                "cited_tool_call_ids": [c["tool_call_id"] for c in cited],
                "counts": counts,
                "pattern": kind,
                "explanation": f"The session's {target} is {n}: it {PATTERNS[target][kind]}.",
            }
            diagnosed.append(d)
            (out / f"{p['session_id']}.json").write_text(json.dumps(d, indent=2) + "\n", newline="\n")
        hit = {d["session_id"] for d in diagnosed}
        summary = {
            "target": target,
            "threshold": threshold,
            "sessions": len(sessions),
            "with_signal": len(diagnosed),
            "credits_with_signal": sum(credits[s] for s in hit),
            "patterns": {k: sum(d["pattern"] == k for d in diagnosed) for k in PATTERNS[target]},
            "unexplained": sorted(s for s, c in credits.items() if c >= cutoff and s not in hit),
            "unexplained_rule": "costliest quarter of derivation sessions (factory_credits) without the signal",
        }
        (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", newline="\n")
        print(json.dumps({k: v for k, v in summary.items() if k != "unexplained"}))
        print(f"  unexplained: {len(summary['unexplained'])} of the costliest quarter")


if __name__ == "__main__":
    main()
