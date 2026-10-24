#!/usr/bin/env python3
"""Droid PostToolUse hook: snapshot the working tree, log one line per tool call.

Appends to $RETRACE_CAPTURE_DIR/<session_id>.jsonl (default ~/.retrace/capture). Stdlib only, because
SWE-bench images ship no jq.
"""
import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

event = json.load(sys.stdin)
snapshot = Path(__file__).with_name("snapshot.sh")
ref = subprocess.run([snapshot, event["cwd"]], capture_output=True, text=True, check=True).stdout.strip()

log_dir = Path(os.environ.get("RETRACE_CAPTURE_DIR", Path.home() / ".retrace" / "capture"))
log_dir.mkdir(parents=True, exist_ok=True)
line = json.dumps({
    "session_id": event["session_id"],
    "tool_name": event["tool_name"],
    "tool_input": event["tool_input"],
    "snapshot_ref": ref,
}) + "\n"
with open(log_dir / f"{event['session_id']}.jsonl", "a") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    f.write(line)
