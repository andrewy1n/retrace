#!/usr/bin/env python3
"""Write dashboard/sources/proposal_list/proposals.csv from analysis/proposals and runs/jobs.

One row per proposal.json. A candidate job names the proposal in arm.path. Its control job is
`<name>-control` when the candidate job is `<name>-candidate`, else a control job with the same
task_ids. When several controls share those tasks, the one with the longest shared job-id prefix
wins. When that still ties and the candidate id starts with r<round>, the control is the latest
earlier round on those tasks. Several candidates may share one control.
The row holds no result. The page joins it to Tiger.
With no proposal the file holds one empty row, because Evidence writes no table for an empty file. Pages filter on proposal_id.
"""
import argparse
import csv
import difflib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["proposal_id", "failure_type", "cost_pattern", "change_type", "path", "pr_url",
           "pairs", "overlay_files", "patch"]
MAX_PATCH_BYTES = 60000


def load_jobs(jobs_dir):
    jobs = []
    for f in sorted(jobs_dir.glob("*.json")):
        job = json.loads(f.read_text())
        if job.get("start") == "step0":
            jobs.append(job)
    return jobs


def _prefix_len(a, b):
    n = 0
    for x, y in zip(a.split("-"), b.split("-")):
        if x != y:
            break
        n += 1
    return n


def _round(job_id):
    head = job_id.split("-", 1)[0]
    return int(head[1:]) if len(head) > 1 and head[0] == "r" and head[1:].isdigit() else None


def control_for(candidate, jobs):
    controls = [j for j in jobs if j["arm"]["kind"] == "control"]
    if candidate["job_id"].endswith("-candidate"):
        name = candidate["job_id"][: -len("candidate")] + "control"
        named = [j for j in controls if j["job_id"] == name]
        if named:
            return named[0]
    same = [j for j in controls if set(j["task_ids"]) == set(candidate["task_ids"])]
    if len(same) <= 1:
        return same[0] if same else None
    best = max(_prefix_len(candidate["job_id"], j["job_id"]) for j in same)
    tied = [j for j in same if _prefix_len(candidate["job_id"], j["job_id"]) == best]
    if len(tied) == 1:
        return tied[0]
    cand_round = _round(candidate["job_id"])
    if cand_round is None:
        return None
    earlier = [j for j in tied if _round(j["job_id"]) is not None and _round(j["job_id"]) <= cand_round]
    if not earlier:
        return None
    top = max(_round(j["job_id"]) for j in earlier)
    picked = [j for j in earlier if _round(j["job_id"]) == top]
    return picked[0] if len(picked) == 1 else None


def pairs_for(path, jobs):
    out = []
    for j in jobs:
        if j["arm"]["kind"] == "candidate" and j["arm"]["path"].rstrip("/") == path.rstrip("/"):
            c = control_for(j, jobs)
            if c:
                out.append(f"{c['job_id']}:{j['job_id']}")
    return out


def overlay(proposal_dir):
    files = sorted(p.relative_to(proposal_dir) for p in (proposal_dir / ".factory").rglob("*") if p.is_file())
    if (proposal_dir / "AGENTS.md").is_file():
        files.append(Path("AGENTS.md"))
    patch = []
    for rel in files:
        lines = (proposal_dir / rel).read_text(errors="replace").splitlines(keepends=True)
        patch += [f"diff --git a/{rel} b/{rel}\n", "new file mode 100644\n"]
        patch += difflib.unified_diff([], lines, "/dev/null", f"b/{rel}")
    text = "".join(patch)
    return ";".join(str(f) for f in files), text[:MAX_PATCH_BYTES]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--proposals", type=Path, default=ROOT / "analysis" / "proposals")
    ap.add_argument("--jobs", type=Path, default=ROOT / "runs" / "jobs")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "sources" / "proposal_list" / "proposals.csv")
    args = ap.parse_args(argv)

    jobs = load_jobs(args.jobs)
    rows = []
    for f in sorted(args.proposals.glob("*/proposal.json")):
        p = json.loads(f.read_text())
        files, patch = overlay(f.parent)
        rows.append({
            "proposal_id": p["proposal_id"],
            "failure_type": p.get("failure_type", ""),
            "cost_pattern": p.get("cost_pattern", ""),
            "change_type": p["change_type"],
            "path": p["path"],
            "pr_url": p.get("pr_url", ""),
            "pairs": ";".join(pairs_for(p["path"], jobs)),
            "overlay_files": files,
            "patch": patch,
        })
    written = len(rows)
    rows = rows or [dict.fromkeys(COLUMNS, "")]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"proposal_list: {written} proposals")


if __name__ == "__main__":
    main()
