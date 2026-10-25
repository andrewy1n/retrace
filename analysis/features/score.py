"""Score each cost feature on the derivation tasks: does it explain credits within a task?

  python analysis/features/score.py [--splits splits/<group>.json] [--candidates] [--primitives DIR] [--jobs DIR]

The discovery scoring rule from the project doc (Open). The model is
log(credits) = task effect + beta * log(1 + feature). The task effect is removed by
subtracting each task's mean, so only differences between runs of the same task count.
Each task is left out in turn: beta is fit on the other tasks and scored on the left-out
one. The score is the share of within-task variance explained out of task (1 - SSE / SST),
summed over left-out tasks. Above 0 means the feature predicts cost on tasks it was not fit on.

"Beyond length" adds log(tool_calls) to both fits, and scores what the feature adds to
session length alone. A feature that only says "the session was long" scores near 0 there.

Reads runs/primitives and runs/jobs only: control-arm step0 sessions of the split's
derivation tasks. No grader output, and no held-out or regression task. --candidates also
scores the unpromoted features in candidates.py.
"""

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from candidates import CANDIDATES
from features import FEATURES, features

ROOT = Path(__file__).resolve().parents[2]


def load(args, derivation, extra):
    jobs = {}
    rows = defaultdict(list)  # task_id -> [(features, log credits, log tool calls)]
    timed_out = 0
    for path in sorted(args.primitives.glob("*.json")):
        p = json.loads(path.read_text())
        if p["task_id"] not in derivation:
            continue
        if p["job_id"] not in jobs:
            jobs[p["job_id"]] = json.loads((args.jobs / f"{p['job_id']}.json").read_text())
        job = jobs[p["job_id"]]
        if job.get("start") != "step0" or job["arm"]["kind"] != "control":
            continue
        credits = float(p["token_usage"]["factory_credits"])
        if credits <= 0:
            continue
        timed_out += bool(p.get("timed_out"))
        values = {**features(p), **{name: f(p["calls"]) for name, f in extra.items()}}
        rows[p["task_id"]].append((values, math.log(credits), math.log(1 + p["tool_calls"])))
    return {t: r for t, r in rows.items() if len(r) >= 2}, timed_out


def demean(xs):
    m = statistics.mean(xs)
    return [x - m for x in xs]


def fit(points):
    """OLS through the origin on demeaned points [(y, x1, x2 or None)]. Returns (b1, b2)."""
    if points[0][2] is None:
        sxx = sum(x * x for _, x, _ in points)
        return (sum(y * x for y, x, _ in points) / sxx if sxx else 0.0), 0.0
    a = sum(x * x for _, x, _ in points)
    b = sum(x * z for _, x, z in points)
    c = sum(z * z for _, _, z in points)
    d = a * c - b * b
    if abs(d) < 1e-12:  # the feature never varies: length alone
        return 0.0, (sum(y * z for y, _, z in points) / c if c else 0.0)
    sy1 = sum(y * x for y, x, _ in points)
    sy2 = sum(y * z for y, _, z in points)
    return (c * sy1 - b * sy2) / d, (a * sy2 - b * sy1) / d


def task_points(rows, feature, with_length):
    out = {}
    for task, rs in rows.items():
        ys = demean([y for _, y, _ in rs])
        xs = demean([math.log1p(f[feature]) for f, _, _ in rs])
        zs = demean([z for _, _, z in rs]) if with_length else [None] * len(rs)
        out[task] = list(zip(ys, xs, zs))
    return out


def loto_score(points_by_task):
    sse = sst = 0.0
    for task, held in points_by_task.items():
        b1, b2 = fit([p for t, ps in points_by_task.items() if t != task for p in ps])
        for y, x, z in held:
            pred = b1 * x + (b2 * z if z is not None else 0.0)
            sse += (y - pred) ** 2
            sst += y * y
    return 1 - sse / sst if sst else float("nan")


def length_points(rows):
    """Session length as the only regressor, in the x slot."""
    return {t: [(y, z, None) for y, _, z in ps] for t, ps in task_points(rows, next(iter(FEATURES)), True).items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--splits", type=Path, default=ROOT / "splits" / "calls_before_first_edit.json")
    ap.add_argument("--candidates", action="store_true", help="also score candidates.py")
    ap.add_argument("--primitives", type=Path, default=ROOT / "runs" / "primitives")
    ap.add_argument("--jobs", type=Path, default=ROOT / "runs" / "jobs")
    args = ap.parse_args()

    derivation = set(json.loads(args.splits.read_text())["derivation"])
    extra = CANDIDATES if args.candidates else {}
    rows, timed_out = load(args, derivation, extra)
    n = sum(map(len, rows.values()))
    print(f"{args.splits.name}: {len(rows)} derivation tasks, {n} control sessions ({timed_out} timed out)")
    length_only = loto_score(length_points(rows))
    print(f"log(tool_calls) alone explains {length_only:.0%} of within-task variance out of task\n")

    print(f"  {'feature':<24}{'tasks where it varies':>22}{'beta':>7}{'out-of-task score':>19}{'beyond length':>15}")
    for feature in [*FEATURES, *extra]:
        if feature in extra and feature == next(iter(extra)):
            print("  candidates")
        varies = sum(len({f[feature] for f, _, _ in rs}) > 1 for rs in rows.values())
        alone = task_points(rows, feature, False)
        beta = fit([p for ps in alone.values() for p in ps])[0]
        score = loto_score(alone)
        beyond = loto_score(task_points(rows, feature, True)) - length_only
        print(f"  {feature:<24}{varies:>22}{beta:>7.2f}{score:>19.0%}{beyond:>+15.0%}")


if __name__ == "__main__":
    main()
