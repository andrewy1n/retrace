"""Compute the session features in analysis/AGENTS.md for recorded sessions.

  python analysis/features/compute.py --sessions DIR [--tasks DIR] [--repos DIR] [--traces DIR] [--results DIR] [--out DIR] [SESSION_ID ...]

With no session ids, it computes every trace in --traces. Records print to stdout
unless --out is given; pass --out runs/features only for real sessions.
"""

import argparse
import json
import sys
from pathlib import Path

from rules import compute
from session import DEFAULT_REPOS, load_session

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", type=Path, default=ROOT / "runs" / "traces")
    ap.add_argument("--results", type=Path, default=ROOT / "runs" / "results")
    ap.add_argument("--sessions", type=Path, required=True, help="directory of session folders")
    ap.add_argument("--tasks", type=Path, default=ROOT / "runs" / "private" / "tasks",
                    help="directory of <task-id>.json from fetch_tasks.py")
    ap.add_argument("--repos", type=Path, default=DEFAULT_REPOS, help="shared upstream repos for real sessions")
    ap.add_argument("--primitives", type=Path, default=ROOT / "runs" / "primitives",
                    help="runs/primitives; a session without a file there falls back to its transcript")
    ap.add_argument("--out", type=Path, help="write <session-id>.json here instead of printing")
    ap.add_argument("session_ids", nargs="*")
    args = ap.parse_args(argv)

    ids = args.session_ids or sorted(p.stem for p in args.traces.glob("*.json"))
    failed = 0
    for sid in ids:
        try:
            row = compute(load_session(sid, args.traces, args.results, args.sessions, args.tasks, args.repos,
                                     args.primitives))
        except Exception as e:  # one bad session should not stop the rest
            print(f"{sid}: {type(e).__name__}: {e}", file=sys.stderr)
            failed += 1
            continue
        text = json.dumps(row, indent=2) + "\n"
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / f"{sid}.json").write_text(text, newline="\n")
        else:
            sys.stdout.write(text)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
