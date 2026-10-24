"""Write runs/private/tasks/<task-id>.json for every task that has a trace.

  python analysis/labeler/fetch_tasks.py [--traces DIR] [--out DIR]

Each file holds instance_id, repo, base_commit, and gold_files: the paths the
dataset's gold patch touches. The patch text, tests, and problem statement are
not saved, and neither is any task without a trace, so held-out tasks never
land on disk. The gold files are for labeling only and never reach the agent.
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET = "SWE-bench/SWE-bench_Verified"  # the dataset recorder/worker runs
API = "https://datasets-server.huggingface.co/rows"
PAGE = 100


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
        page = get({"dataset": DATASET, "config": "default", "split": "test", "offset": offset, "length": PAGE})
        total = page["num_rows_total"]
        for item in page["rows"]:
            yield item["row"]
        offset += PAGE


def gold_files(patch):
    """Paths on the --- a/ and +++ b/ lines, so added and deleted files count too."""
    paths = []
    for line in patch.splitlines():
        for prefix in ("--- a/", "+++ b/"):
            if line.startswith(prefix) and line[len(prefix):] not in paths:
                paths.append(line[len(prefix):])
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", type=Path, default=ROOT / "runs" / "traces")
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "private" / "tasks")
    args = ap.parse_args()

    wanted = {json.loads(p.read_text())["task_id"] for p in args.traces.glob("*.json")}
    args.out.mkdir(parents=True, exist_ok=True)
    found = set()
    for row in dataset_rows():
        if row["instance_id"] not in wanted:
            continue
        task = {
            "instance_id": row["instance_id"],
            "repo": row["repo"],
            "base_commit": row["base_commit"],
            "gold_files": gold_files(row["patch"]),
        }
        (args.out / f"{row['instance_id']}.json").write_text(json.dumps(task, indent=2) + "\n", newline="\n")
        found.add(row["instance_id"])
    missing = sorted(wanted - found)
    print(f"wrote {len(found)} tasks to {args.out}")
    if missing:
        sys.exit(f"not in {DATASET}: {', '.join(missing)}")


if __name__ == "__main__":
    main()
