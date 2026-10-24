"""Draw splits/pool.json from SWE-bench Verified by repo and difficulty quota.

  python splits/draw_pool.py [--out splits/pool.json]

Reads only instance_id, repo, and difficulty. Problem statements, patches, and
tests never touch disk. Each (split, repo, difficulty) bucket is shuffled with
its own seed, so changing one quota leaves the other buckets' picks unchanged.
The next SPARES ids in each bucket are kept as spares for gold-check failures.
"""

import argparse
import json
import random
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = "SWE-bench/SWE-bench_Verified"
API = "https://datasets-server.huggingface.co/rows"
SEED = 11
SPARES = 2
MID, HARD = "15 min - 1 hour", "1-4 hours"

KEEP_DEV = json.loads((ROOT / "runs" / "jobs" / "baseline1.json").read_text())["task_ids"]

QUOTAS = {
    "dev": [
        ("django/django", MID, 2), ("django/django", HARD, 4),
        ("sympy/sympy", MID, 2), ("sympy/sympy", HARD, 2),
        ("sphinx-doc/sphinx", MID, 6), ("sphinx-doc/sphinx", HARD, 2),
        ("pytest-dev/pytest", MID, 4), ("pytest-dev/pytest", HARD, 2),
        ("pylint-dev/pylint", MID, 3), ("pylint-dev/pylint", HARD, 1),
        ("psf/requests", MID, 2),
    ],
    "held_out": [
        ("matplotlib/matplotlib", MID, 6),
        ("scikit-learn/scikit-learn", MID, 6), ("scikit-learn/scikit-learn", HARD, 1),
        ("pydata/xarray", MID, 6), ("pydata/xarray", HARD, 1),
        ("astropy/astropy", MID, 6), ("astropy/astropy", HARD, 3),
    ],
}


def get(params, tries=3):
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def dataset_rows():
    offset, total = 0, None
    while total is None or offset < total:
        page = get({"dataset": DATASET, "config": "default", "split": "test", "offset": offset, "length": 100})
        total = page["num_rows_total"]
        for item in page["rows"]:
            r = item["row"]
            yield {"instance_id": r["instance_id"], "repo": r["repo"], "difficulty": r["difficulty"]}
        offset += 100


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "splits" / "pool.json")
    args = ap.parse_args()

    rows = list(dataset_rows())
    dev_repos = {repo for repo, _, _ in QUOTAS["dev"]} | {r["repo"] for r in rows if r["instance_id"] in KEEP_DEV}
    held_repos = {repo for repo, _, _ in QUOTAS["held_out"]}
    assert not dev_repos & held_repos, dev_repos & held_repos

    pool = {"dev": list(KEEP_DEV), "held_out": []}
    spares = {"dev": [], "held_out": []}
    for split, quotas in QUOTAS.items():
        for repo, band, n in quotas:
            bucket = sorted(r["instance_id"] for r in rows
                            if r["repo"] == repo and r["difficulty"] == band and r["instance_id"] not in KEEP_DEV)
            random.Random(f"{SEED}/{split}/{repo}/{band}").shuffle(bucket)
            if len(bucket) < n:
                raise SystemExit(f"{split} {repo} {band}: want {n}, have {len(bucket)}")
            pool[split] += bucket[:n]
            spares[split] += bucket[n:n + SPARES]

    out = {
        "drawn": date.today().isoformat(),
        "seed": SEED,
        "source": f"{DATASET}. Drawn by splits/draw_pool.py from the quotas in that file. "
                  "Dev keeps the 26 baseline1 tasks. Held-out repos (matplotlib, scikit-learn, xarray, astropy) "
                  "were chosen for large test suites, before any run on them, and appear nowhere in dev.",
        "gold_check": "TBD",
        "dev": pool["dev"],
        "held_out": pool["held_out"],
        "spares": spares,
    }
    args.out.write_text(json.dumps(out, indent=2) + "\n", newline="\n")
    print(f"dev {len(pool['dev'])} ({len(pool['dev']) - len(KEEP_DEV)} new), held_out {len(pool['held_out'])}, "
          f"spares {len(spares['dev'])} + {len(spares['held_out'])} -> {args.out}")


if __name__ == "__main__":
    main()
