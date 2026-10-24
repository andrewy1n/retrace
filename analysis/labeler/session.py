"""Load one recorded session for the labeler.

A session is spread over four places:

  traces/<session-id>.json         steps and snapshot refs (contracts/trace.schema.json)
  results/**/<...>.json            the trial whose session_id matches (contracts/replay-result.schema.json)
  sessions/<session-id>/           start_commit, the snapshots, and factory-sessions/ (recorder/AGENTS.md)
  tasks/<task-id>.json             gold_files for the task (mocks only for now)
"""

import json
from dataclasses import dataclass
from pathlib import Path

# The Execute tool's input key for its shell command. Unverified: confirm on the first real trace.
EXECUTE = "Execute"
COMMAND_KEY = "command"


@dataclass
class Session:
    session_id: str
    trace: dict
    result: dict
    start_commit: str
    repo: Path
    commands: dict  # tool_call_id -> shell command, for Execute calls
    gold_files: list


def open_repo(session_dir):
    """Return a git repo that holds the session's snapshots under refs/retrace/."""
    if (session_dir / "repo").is_dir():
        return session_dir / "repo"
    if (session_dir / "snapshots.bundle").exists():
        # Step 6: clone the upstream repo at base_commit, then fetch the bundle (recorder/AGENTS.md).
        raise NotImplementedError(f"{session_dir}: loading snapshots.bundle is not built yet")
    raise FileNotFoundError(f"{session_dir}: no repo/ and no snapshots.bundle")


def find_result(results_dir, session_id):
    matches = []
    for path in sorted(Path(results_dir).rglob("*.json")):
        row = json.loads(path.read_text())
        if isinstance(row, dict) and row.get("session_id") == session_id:
            matches.append(row)
    if len(matches) != 1:
        raise LookupError(f"{session_id}: expected 1 result with this session_id, found {len(matches)}")
    return matches[0]


def find_transcript(session_dir, harness_session_id):
    """The Droid session file whose session_start id matches. A run can leave several."""
    for path in sorted((session_dir / "factory-sessions").rglob("*.jsonl")):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row.get("type") == "session_start":
                if row.get("id") == harness_session_id:
                    return path
                break
    raise LookupError(f"{session_dir}: no Droid session file with id {harness_session_id}")


def read_commands(transcript):
    commands = {}
    for line in transcript.read_text().splitlines():
        row = json.loads(line)
        message = row.get("message") or {}
        if row.get("type") != "message" or message.get("role") != "assistant":
            continue
        for block in message.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == EXECUTE:
                commands[block["id"]] = (block.get("input") or {}).get(COMMAND_KEY, "")
    return commands


def load_session(session_id, traces_dir, results_dir, sessions_dir, tasks_dir):
    trace = json.loads((Path(traces_dir) / f"{session_id}.json").read_text())
    session_dir = Path(sessions_dir) / session_id
    task = json.loads((Path(tasks_dir) / f"{trace['task_id']}.json").read_text())
    return Session(
        session_id=session_id,
        trace=trace,
        result=find_result(results_dir, session_id),
        start_commit=(session_dir / "start_commit").read_text().strip(),
        repo=open_repo(session_dir),
        commands=read_commands(find_transcript(session_dir, trace["harness_session_id"])),
        gold_files=task["gold_files"],
    )
