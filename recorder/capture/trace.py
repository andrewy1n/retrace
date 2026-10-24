#!/usr/bin/env python3
"""Write runs/traces/<session-id>.json from a Droid transcript and a hook.py capture log.

  trace.py --session-id ID --task-id TASK --transcript T.jsonl --capture C.jsonl [--out DIR]

Each tool_use in the transcript becomes a step. Its snapshot_ref comes from the capture line with the
same tool_name and tool_input, taken in order. Droid runs no PostToolUse hook for a failed tool call, so
such a call takes the previous step's snapshot_ref. A failed call before any snapshot is dropped.
"""
import argparse
import json
import os
import sys
from collections import defaultdict, deque
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(os.environ.get("RETRACE_REPO", Path(__file__).resolve().parents[2]))


def key(name, tool_input):
    return name, json.dumps(tool_input, sort_keys=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--out", default=REPO / "runs" / "traces")
    args = ap.parse_args()

    refs = defaultdict(deque)
    for line in Path(args.capture).read_text().splitlines():
        row = json.loads(line)
        refs[key(row["tool_name"], row["tool_input"])].append(row["snapshot_ref"])

    harness_session_id, steps, inherited, dropped, last_ref = None, [], 0, 0, None
    for line in Path(args.transcript).read_text().splitlines():
        row = json.loads(line)
        if row.get("type") == "session_start":
            harness_session_id = row["id"]
        message = row.get("message") or {}
        if row.get("type") != "message" or message.get("role") != "assistant":
            continue
        for block in message["content"]:
            if block.get("type") != "tool_use":
                continue
            queue = refs[key(block["name"], block["input"])]
            if queue:
                last_ref = queue.popleft()
            elif last_ref:
                inherited += 1
            else:
                dropped += 1
                continue
            steps.append({
                "tool_call_id": block["id"],
                "message_id": row["id"],
                "tool_name": block["name"],
                "snapshot_ref": last_ref,
            })

    trace = {
        "session_id": args.session_id,
        "harness": "droid",
        "task_id": args.task_id,
        "harness_session_id": harness_session_id,
        "steps": steps,
    }
    schema = json.loads((REPO / "contracts" / "trace.schema.json").read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(trace), key=str)
    if errors:
        sys.exit("trace.schema.json: " + "; ".join(e.message for e in errors))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.session_id}.json").write_text(json.dumps(trace, indent=2) + "\n")
    print(f"{args.session_id}: {len(steps)} steps, {inherited} with the previous snapshot, {dropped} dropped")


main()
