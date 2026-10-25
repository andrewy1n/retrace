"""Draw splits/<group>.json from splits/pro-pool.json: derivation, held-out, and regression.

  python splits/pro_split.py --group <target> [--out PATH]

A seeded shuffle within each dev repo picks the regression tasks, so no one picks them by hand
and no outcome is read. Regression tasks leave derivation, as AGENTS.md (Grader) requires.
Held-out is the pool's held_out list unchanged. The draw does not depend on --group, so a
draft and the final file hold the same ids.
"""

import argparse
import json
import random
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 19
REGRESSION_PER_REPO = 2


def repo_of(instance_id):
    owner, rest = instance_id.removeprefix("instance_").split("__", 1)
    return f"{owner}/{rest.split('-')[0]}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--group", required=True, help="the target: a promoted feature name or a failure type")
    ap.add_argument("--out", type=Path, help="default splits/<group>.json")
    args = ap.parse_args()

    pool = json.loads((ROOT / "splits" / "pro-pool.json").read_text())
    by_repo = {}
    for i in pool["dev"]:
        by_repo.setdefault(repo_of(i), []).append(i)

    regression = []
    for repo in sorted(by_repo):
        ids = sorted(by_repo[repo])
        random.Random(f"{SEED}/{repo}").shuffle(ids)
        regression += ids[:REGRESSION_PER_REPO]
    derivation = [i for i in pool["dev"] if i not in regression]

    out = {
        "group": args.group,
        "drawn": date.today().isoformat(),
        "seed": SEED,
        "source": f"splits/pro-pool.json (seed {pool['seed']}). Regression is {REGRESSION_PER_REPO} dev tasks per repo "
                  "from a seeded shuffle within each repo, and leaves derivation. Held-out is the pool's held_out list.",
        "derivation": derivation,
        "held_out": pool["held_out"],
        "regression": regression,
    }
    path = args.out or ROOT / "splits" / f"{args.group}.json"
    path.write_text(json.dumps(out, indent=2) + "\n", newline="\n")
    counts = {repo: sum(repo_of(i) == repo for i in derivation) for repo in sorted(by_repo)}
    print(f"{path.name}: derivation {len(derivation)} {counts}, held_out {len(pool['held_out'])}, "
          f"regression {len(regression)}")


if __name__ == "__main__":
    main()
