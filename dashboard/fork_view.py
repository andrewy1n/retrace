#!/usr/bin/env python3
"""Write dashboard/sources/fork_view/calls.csv from the checkpoint jobs in runs/jobs.

One row per tool call of each fork trial and of the recorded session it forked from. A fork keeps the calls before its
checkpoint, so the row says which calls are that shared prefix. `blocked` marks a call that a hook stopped, read from the
private session copy when it exists. The page filters on proposal_path. With no checkpoint job the file holds one empty
row, because Evidence writes no table for an empty file.
"""
import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["proposal_path", "job_id", "arm", "trial", "checkpoint", "fork_position", "position", "tool_call_id",
           "tool_name", "command_class", "label", "is_error", "blocked", "in_prefix", "cost_credits", "duration_s", "output_tokens_est", "files"]
HOOK_BLOCK = re.compile(r"^Error: \[[\w-]+\]")


def blocked_ids(root, name):
    paths = list((root / "runs" / "private" / "sessions" / name).glob("factory-sessions/*/*.jsonl"))
    meta = root / "runs" / "private" / "sessions" / name / "meta.json"
    if not paths or not meta.exists():
        return None
    droid_id = json.loads(meta.read_text()).get("droid_session_id")
    transcript = next((p for p in paths if p.stem == droid_id), None)
    if transcript is None:
        return None
    ids = set()
    for line in transcript.read_text().splitlines():
        content = (json.loads(line).get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_result" and block.get("is_error") and isinstance(block.get("content"), str) \
                    and HOOK_BLOCK.match(block["content"]):
                ids.add(block["tool_use_id"])
    return ids


def result_credits(root, job_id, checkpoint, trial):
    for f in (root / "runs" / "results" / job_id).glob(f"*-{checkpoint}-*-{trial}.json"):
        return json.loads(f.read_text()).get("cost_credits")
    return ""


def row(proposal_path, job_id, arm, trial, checkpoint, fork_position, call, in_prefix, blocked, credits):
    return {"proposal_path": proposal_path, "job_id": job_id, "arm": arm, "trial": trial, "checkpoint": checkpoint,
            "fork_position": fork_position, "position": call["position"], "tool_call_id": call["tool_call_id"],
            "tool_name": call["tool_name"], "command_class": call["command_class"],
            "label": call["test_runner"] or call["tool_name"], "is_error": bool(call["is_error"]),
            "blocked": "" if blocked is None else call["tool_call_id"] in blocked, "in_prefix": in_prefix,
            "cost_credits": credits, "duration_s": call.get("duration_s"), "output_tokens_est": call.get("output_tokens_est"),
            "files": ";".join(call.get("files") or [])}


def build(root):
    jobs = [json.loads(p.read_text()) for p in sorted((root / "runs" / "jobs").glob("*.json"))]
    forks = [j for j in jobs if j["start"] == "checkpoint" and j["arm"]["kind"] in ("control", "candidate")]
    rows = []
    for job in forks:
        recorded_path = root / "runs" / "primitives" / f"{job['session_id']}.json"
        if not recorded_path.exists():
            continue
        recorded = json.loads(recorded_path.read_text())["calls"]
        path = job["arm"].get("path") or next(
            (j["arm"]["path"] for j in forks if j["arm"]["kind"] == "candidate" and j["session_id"] == job["session_id"]
             and j["tool_call_ids"] == job["tool_call_ids"]), "")
        for checkpoint in job["tool_call_ids"]:
            at = next((c["position"] for c in recorded if c["tool_call_id"] == checkpoint), None)
            if at is None:
                continue
            for trial in range(1, job["reruns"] + 1):
                found = sorted((root / "runs" / "primitives").glob(f"{job['job_id']}-*-{trial}.json"))
                if not found:
                    continue
                calls = json.loads(found[0].read_text())["calls"]
                blocked = blocked_ids(root, found[0].stem)
                credits = result_credits(root, job["job_id"], checkpoint, trial)
                rows += [row(path, job["job_id"], job["arm"]["kind"], trial, checkpoint, at, c, c["position"] < at, blocked, credits)
                         for c in calls]
            if not any(r["arm"] == "recorded" and r["checkpoint"] == checkpoint and r["proposal_path"] == path for r in rows):
                rows += [row(path, job["session_id"], "recorded", 0, checkpoint, at, c, c["position"] < at, None, "")
                         for c in recorded]
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out", default=str(Path(__file__).parent / "sources" / "fork_view" / "calls.csv"))
    args = ap.parse_args(argv)
    rows = build(Path(args.root)) or [{c: "" for c in COLUMNS}]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
