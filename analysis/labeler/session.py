"""Load one recorded session for the labeler.

A session is spread over four places:

  traces/<session-id>.json         steps and snapshot refs (contracts/trace.schema.json)
  results/**/<...>.json            the trial whose session_id matches (contracts/replay-result.schema.json)
  sessions/<session-id>/           start_commit, the snapshots, and factory-sessions/ (recorder/AGENTS.md)
  tasks/<task-id>.json             repo, base_commit, gold_files (fetch_tasks.py; mocks write their own)
"""

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from gitdiff import git, has_commit

# The Execute tool's input key for its shell command. Checked on Droid 0.249.0.
EXECUTE = "Execute"
COMMAND_KEY = "command"

# Shared upstream repos for real sessions. Gitignored, like everything under runs/private/.
DEFAULT_REPOS = Path(__file__).resolve().parents[2] / "runs" / "private" / "repos"


@dataclass
class Session:
    session_id: str
    trace: dict
    result: dict
    start_commit: str
    repo: Path
    commands: dict  # tool_call_id -> shell command, for Execute calls; empty when primitives exist
    gold_files: list
    primitives: dict = None  # runs/primitives/<session-id>.json, or None (mocks without one)


def open_repo(session_dir, task, repos_dir, needed):
    """Return a git repo that holds the commits in needed.

    A mock folder has repo/. A real one has snapshots.bundle, whose prerequisite
    is the parent of start_commit (recorder/AGENTS.md). On Verified that is the
    dataset base_commit; on Pro, start_commit is base_commit, so it is an older
    commit. The bundle header names its prerequisites, and each is fetched from
    upstream by id. Real sessions share one repo per upstream under repos_dir,
    and each fetch is skipped once its commits are there.
    """
    if (session_dir / "repo").is_dir():
        return session_dir / "repo"
    bundle = session_dir / "snapshots.bundle"
    if not bundle.exists():
        raise FileNotFoundError(f"{session_dir}: no repo/ and no snapshots.bundle")
    repo = Path(repos_dir) / task["repo"].replace("/", "__")
    if not (repo / ".git").exists():
        repo.mkdir(parents=True, exist_ok=True)
        git(repo, "init", "-q")
    if not all(has_commit(repo, ref) for ref in needed):
        for prereq in bundle_prerequisites(bundle):
            if not has_commit(repo, prereq):
                fetch_upstream(repo, task["repo"], prereq)
        git(repo, "fetch", "-q", str(bundle.resolve()), "refs/retrace/*:refs/retrace/*")
    return repo


def bundle_prerequisites(bundle):
    """Commit ids on the bundle header's "-<id>" lines."""
    with open(bundle, "rb") as f:
        header = f.read(64 * 1024).split(b"\n\n", 1)[0]
    return [line[1:41].decode() for line in header.split(b"\n") if line.startswith(b"-")]


def fetch_upstream(repo, name, commit):
    for attempt in range(3):  # GitHub fetches fail now and then
        try:
            git(repo, "fetch", "-q", "--depth", "1", f"https://github.com/{name}.git", commit)
            break
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    git(repo, "update-ref", f"refs/base/{commit}", commit)  # keeps it from git gc


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


def load_session(session_id, traces_dir, results_dir, sessions_dir, tasks_dir, repos_dir=DEFAULT_REPOS,
                 primitives_dir=None):
    trace = json.loads((Path(traces_dir) / f"{session_id}.json").read_text())
    session_dir = Path(sessions_dir) / session_id
    task = json.loads((Path(tasks_dir) / f"{trace['task_id']}.json").read_text())
    start_commit = (session_dir / "start_commit").read_text().strip()
    needed = [start_commit] + [step["snapshot_ref"] for step in trace["steps"]]
    prim_file = Path(primitives_dir) / f"{session_id}.json" if primitives_dir else None
    primitives = json.loads(prim_file.read_text()) if prim_file and prim_file.exists() else None
    # Primitives classify every call, so the transcript is read only without them.
    commands = {} if primitives else read_commands(find_transcript(session_dir, trace["harness_session_id"]))
    return Session(
        session_id=session_id,
        trace=trace,
        result=find_result(results_dir, session_id),
        start_commit=start_commit,
        repo=open_repo(session_dir, task, repos_dir, needed),
        commands=commands,
        gold_files=task["gold_files"],
        primitives=primitives,
    )
