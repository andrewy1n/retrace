"""Draw splits/pro-candidates.json from SWE-bench Pro V2 (Python and Go repos).

  python splits/pro_candidates.py [--out splits/pro-candidates.json]

Takes PER_REPO tasks from each repo in a seeded shuffle. Tasks whose gold patch touches MIN_FILES or
more files come first. Reads instance_id, repo, patch, and docker_image only.
"""

import argparse
import json
import random
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = "ScaleAI/SWE-bench_Pro"
API = "https://datasets-server.huggingface.co/rows"
SEED = 7
PER_REPO = 8
MIN_FILES = 3
REPOS = [
    "ansible/ansible", "internetarchive/openlibrary", "qutebrowser/qutebrowser",
    "flipt-io/flipt", "gravitational/teleport", "future-architect/vuls", "navidrome/navidrome",
]


def get(params, tries=4):
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def dataset_rows():
    offset, rows = 0, []
    while True:
        page = get({"dataset": DATASET, "config": "default", "split": "test", "offset": offset, "length": 50})
        rows += [r["row"] for r in page["rows"]]
        offset += 50
        if offset >= page["num_rows_total"]:
            return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=ROOT / "splits" / "pro-candidates.json")
    args = ap.parse_args()

    by_repo = {repo: [] for repo in REPOS}
    for row in dataset_rows():
        if row["repo"] in by_repo:
            files = len(re.findall(r"^diff --git ", row["patch"], re.M))
            by_repo[row["repo"]].append((row["instance_id"], files, row["docker_image"]))

    picks = {}
    for repo, tasks in by_repo.items():
        tasks.sort()
        random.Random(f"{SEED}/{repo}").shuffle(tasks)
        tasks.sort(key=lambda t: t[1] < MIN_FILES)
        picks[repo] = [{"instance_id": i, "gold_files": n, "docker_image": img} for i, n, img in tasks[:PER_REPO]]

    out = {"dataset": DATASET, "config": "default", "seed": SEED, "per_repo": PER_REPO, "min_files": MIN_FILES, "repos": picks}
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print({repo: [t["gold_files"] for t in tasks] for repo, tasks in picks.items()})


if __name__ == "__main__":
    main()
