"""Write runs/private/tasks/<task-id>.json for every task that has a trace.

  python analysis/features/fetch_tasks.py [--traces DIR] [--out DIR]

Each file holds instance_id, repo, and base_commit, which the snapshot loader
needs. No other column is read, so nothing the grader uses reaches feature
computation (the Grader section of AGENTS.md). Tasks without a trace are skipped, so
held-out tasks never land on disk.
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The datasets recorder/worker runs. Pro ids start with instance_, so ids never collide.
DATASETS = ["SWE-bench/SWE-bench_Verified", "ScaleAI/SWE-bench_Pro"]
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


def dataset_rows(dataset):
    offset, total = 0, None
    while total is None or offset < total:
        page = get({"dataset": dataset, "config": "default", "split": "test", "offset": offset, "length": PAGE})
        total = page["num_rows_total"]
        for item in page["rows"]:
            yield item["row"]
        offset += PAGE


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", type=Path, default=ROOT / "runs" / "traces")
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "private" / "tasks")
    args = ap.parse_args()

    wanted = {json.loads(p.read_text())["task_id"] for p in args.traces.glob("*.json")}
    args.out.mkdir(parents=True, exist_ok=True)
    found = set()
    for row in (row for dataset in DATASETS for row in dataset_rows(dataset)):
        if row["instance_id"] not in wanted:
            continue
        task = {key: row[key] for key in ("instance_id", "repo", "base_commit")}
        (args.out / f"{row['instance_id']}.json").write_text(json.dumps(task, indent=2) + "\n", newline="\n")
        found.add(row["instance_id"])
    missing = sorted(wanted - found)
    print(f"wrote {len(found)} tasks to {args.out}")
    if missing:
        sys.exit(f"not in {' or '.join(DATASETS)}: {', '.join(missing)}")


if __name__ == "__main__":
    main()
