"""Draw a second held-out set from the held-out repos of splits/pro-pool.json, for round 2.

  python splits/pro_heldout2.py draw      # writes splits/pro-heldout2-candidates.json
  python splits/pro_heldout2.py select    # reads splits/pro-heldout2-gold-check.json, writes splits/pro-heldout2.json

draw continues the seeded order of splits/pro_candidates.py within each held-out repo, past the tasks that file
already holds, and takes the next DRAW_PER_REPO. select keeps, per repo and in that order, the first KEEP_PER_REPO
tasks whose gold patch passes and whose empty patch fails. Neither step reads an agent outcome.
"""

import json
import random
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pro_candidates import DATASET, MIN_FILES, SEED, dataset_rows

ROOT = Path(__file__).resolve().parents[1]
DRAW_PER_REPO = 11
KEEP_PER_REPO = 8
CANDIDATES = ROOT / "splits" / "pro-heldout2-candidates.json"
GOLD = ROOT / "splits" / "pro-heldout2-gold-check.json"
OUT = ROOT / "splits" / "pro-heldout2.json"


def draw():
    pool = json.loads((ROOT / "splits" / "pro-pool.json").read_text())
    used = {t["instance_id"] for ts in json.loads((ROOT / "splits" / "pro-candidates.json").read_text())["repos"].values()
            for t in ts}
    ran = {json.loads(p.read_text())["task_id"] for p in (ROOT / "runs" / "results").glob("*/*.json")}
    by_repo = {repo: [] for repo in pool["held_out_repos"]}
    for row in dataset_rows():
        if row["repo"] in by_repo:
            files = len(re.findall(r"^diff --git ", row["patch"], re.M))
            by_repo[row["repo"]].append((row["instance_id"], files, row["docker_image"]))
    picks = {}
    for repo, tasks in by_repo.items():
        tasks.sort()
        random.Random(f"{SEED}/{repo}").shuffle(tasks)
        tasks.sort(key=lambda t: t[1] < MIN_FILES)
        fresh = [t for t in tasks if t[0] not in used and t[0] not in ran]
        picks[repo] = [{"instance_id": i, "gold_files": n, "docker_image": img} for i, n, img in fresh[:DRAW_PER_REPO]]
    out = {"dataset": DATASET, "config": "default", "seed": SEED, "draw_per_repo": DRAW_PER_REPO,
           "min_files": MIN_FILES, "repos": picks}
    CANDIDATES.write_text(json.dumps(out, indent=2) + "\n")
    print({repo: [t["gold_files"] for t in ts] for repo, ts in picks.items()})


def select():
    cands = json.loads(CANDIDATES.read_text())
    ok = {c["instance_id"] for c in json.loads(GOLD.read_text()) if c["gold_reward"] == 1 and c["empty_reward"] == 0}
    held_out = []
    for repo, ts in cands["repos"].items():
        keep = [t["instance_id"] for t in ts if t["instance_id"] in ok][:KEEP_PER_REPO]
        print(f"{repo}: {len(keep)} of {len(ts)}")
        held_out += keep
    out = {
        "drawn": date.today().isoformat(),
        "seed": SEED,
        "source": "splits/pro_heldout2.py: the seeded order of splits/pro_candidates.py within the held-out repos of "
                  "splits/pro-pool.json, past the tasks splits/pro-candidates.json holds, keeping per repo the first "
                  f"{KEEP_PER_REPO} that pass the gold patch and fail the empty patch (splits/pro-heldout2-gold-check.json). "
                  "No agent ran any of them before the draw.",
        "held_out_repos": list(cands["repos"]),
        "held_out": held_out,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    {"draw": draw, "select": select}[sys.argv[1]]()
