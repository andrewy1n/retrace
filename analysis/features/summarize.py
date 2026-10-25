"""Print how common each cost feature is, and what sessions with it cost.

  python analysis/features/summarize.py [--primitives DIR] [--jobs DIR]

Reads only runs/primitives and runs/jobs, both in git, and no grader output.
Groups sessions by the job's dataset (swebench_verified when the job names
none). Credits are the session's factory_credits. This shows correlation, not
cause: only step-0 replay shows that removing a pattern saves credits.
"""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from features import FEATURES, features

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--primitives", type=Path, default=ROOT / "runs" / "primitives")
    ap.add_argument("--jobs", type=Path, default=ROOT / "runs" / "jobs")
    args = ap.parse_args()

    def dataset(job_id):
        job = args.jobs / f"{job_id}.json"
        return json.loads(job.read_text()).get("dataset", "swebench_verified") if job.exists() else "unknown job"

    groups = defaultdict(list)
    for path in sorted(args.primitives.glob("*.json")):
        p = json.loads(path.read_text())
        groups[dataset(p["job_id"])].append((features(p), float(p["token_usage"]["factory_credits"])))

    for name, rows in sorted(groups.items()):
        credits = [c for _, c in rows]
        print(f"\n{name}: {len(rows)} sessions, credits median {statistics.median(credits):,.0f}, "
              f"mean {statistics.mean(credits):,.0f}")
        print(f"  {'feature':<24}{'sessions with it':>18}{'mean credits with':>20}{'without':>10}")
        for feature in FEATURES:
            with_it = [c for f, c in rows if f[feature] > 0]
            without = [c for f, c in rows if f[feature] == 0]
            share = f"{len(with_it)} ({len(with_it) / len(rows):.0%})"
            mean = lambda xs: f"{statistics.mean(xs):,.0f}" if xs else "-"
            print(f"  {feature:<24}{share:>18}{mean(with_it):>20}{mean(without):>10}")


if __name__ == "__main__":
    main()
