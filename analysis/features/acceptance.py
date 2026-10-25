"""Prepare the inputs for an acceptance check, and validate a written one.

An acceptance check (contracts/acceptance-check.schema.json) is written from two inputs only:
the task's instruction and the repo at the start commit. The Grader section of AGENTS.md
keeps everything else out: no reference fix, no dataset tests or test lists, no replay
result, and no agent snapshot. So `prepare` copies just those two inputs into a
scratch folder outside this repo, and the author reads only that folder.

  python analysis/features/acceptance.py prepare <task-id> [--out <dir>]
  python analysis/features/acceptance.py check <task-id>... [--draft]
  python analysis/features/acceptance.py freeze <task-id>...

prepare finds one recorded session of the task under runs/private/sessions/ for its
start_commit. The instruction is that session's prompt.md on Verified, and on Pro it is
instruction.md under /opt/retrace/swe-bench-pro/v2/tasks/<instance_id>/, read from the worker
over SSH (vm_host in retrace.local.json). The repo comes from the shared repo under
runs/private/repos/ (session.open_repo), read by `git cat-file` at start_commit alone.
It refuses a held-out task.

check validates runs/acceptance/<task-id>/check.json and files/<path>. --draft accepts a
missing frozen_at, which Kate sets at commit, or freeze sets to now.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from gitdiff import git
from session import DEFAULT_REPOS, open_repo

ROOT = Path(__file__).resolve().parents[2]
SESSIONS = ROOT / "runs" / "private" / "sessions"
TASKS = ROOT / "runs" / "private" / "tasks"
ACCEPTANCE = ROOT / "runs" / "acceptance"
SCHEMA = ROOT / "contracts" / "acceptance-check.schema.json"
SPLITS = (ROOT / "splits" / "pool.json", ROOT / "splits" / "pro-pool.json")
PRO_TASKS = "/opt/retrace/swe-bench-pro/v2/tasks"
SCRATCH = Path(tempfile.gettempdir()) / "retrace-acceptance"
TASK_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def dataset_of(task_id):
    return "swebench_pro" if task_id.startswith("instance_") else "swebench_verified"


def held_out():
    ids = set()
    for path in SPLITS:
        split = json.loads(path.read_text())
        ids.update(split.get("held_out", []))
        ids.update(split.get("spares", {}).get("held_out", []))
    return ids


def find_session(task_id):
    """A session folder of the task, named <job>-<task-id>-<trial>, that has a start_commit."""
    for path in sorted(SESSIONS.glob(f"*-{task_id}-*")):
        rest = path.name.rsplit(f"-{task_id}-", 1)
        if len(rest) == 2 and rest[1].isdigit() and (path / "start_commit").exists():
            return path
    raise LookupError(f"{task_id}: no session under {SESSIONS} with a start_commit")


def read_instruction(task_id, session_dir):
    if dataset_of(task_id) == "swebench_verified":
        return (session_dir / "prompt.md").read_text(encoding="utf-8")
    host = json.loads((ROOT / "retrace.local.json").read_text())["vm_host"]
    run = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", f"root@{host}", "cat", f"{PRO_TASKS}/{task_id}/instruction.md"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if run.returncode != 0:
        raise RuntimeError(f"{task_id}: reading instruction.md on the worker failed: "
                           + run.stderr.replace(host, "<vm_host>").strip())
    return run.stdout


def export_tree(repo, commit, out):
    """Write every regular file at commit into out. Symlinks and submodules are listed, not written."""
    entries, skipped = [], []
    for row in git(repo, "ls-tree", "-r", "-z", commit).split("\0")[:-1]:
        meta, path = row.split("\t", 1)
        mode, kind, blob = meta.split()
        (entries if kind == "blob" and mode in ("100644", "100755") else skipped).append((path, blob))
    batch = subprocess.run(
        ["git", "cat-file", "--batch"], cwd=repo, check=True, capture_output=True,
        input="".join(f"{blob}\n" for _, blob in entries).encode(),
    ).stdout
    pos = 0
    for path, blob in entries:
        header_end = batch.index(b"\n", pos)
        size = int(batch[pos:header_end].split()[2])
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(batch[header_end + 1:header_end + 1 + size])
        pos = header_end + 1 + size + 1
    return len(entries), [path for path, _ in skipped]


def cmd_prepare(a):
    task_id = a.task_id
    if not TASK_ID.match(task_id):
        raise ValueError(f"{task_id!r} is not a task id")
    if task_id in held_out():
        raise ValueError(f"{task_id} is held out. Its acceptance check is written only after the candidate is frozen.")
    out = Path(a.out).resolve() if a.out else SCRATCH / task_id
    if out == ROOT or ROOT in out.parents:
        raise ValueError(f"{out} is inside the repo. The scratch folder stays outside it.")
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} is not empty")

    session_dir = find_session(task_id)
    start_commit = (session_dir / "start_commit").read_text().strip()
    task = json.loads((TASKS / f"{task_id}.json").read_text())
    repo = open_repo(session_dir, {"repo": task["repo"]}, DEFAULT_REPOS, [start_commit])
    instruction = read_instruction(task_id, session_dir)

    (out / "repo").mkdir(parents=True)
    (out / "instruction.md").write_text(instruction, encoding="utf-8")
    written, skipped = export_tree(repo, start_commit, out / "repo")
    (out / "inputs.json").write_text(json.dumps({
        "task_id": task_id,
        "dataset": dataset_of(task_id),
        "inputs": ["instruction", "start_repo"],
        "start_commit": start_commit,
        "session": session_dir.name,
        "files": written,
        "not_written": skipped,
    }, indent=2) + "\n")
    print(f"{task_id}: instruction.md and {written} files at {start_commit[:12]} in {out}")


def validate(task_id, draft=False):
    """Problems with runs/acceptance/<task-id>/, as a list of strings. Empty means valid."""
    schema = json.loads(SCHEMA.read_text())
    folder = ACCEPTANCE / task_id
    try:
        check = json.loads((folder / "check.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"check.json: {e}"]
    if not isinstance(check, dict):
        return ["check.json is not an object"]
    problems = []
    required = [k for k in schema["required"] if not (draft and k == "frozen_at")]
    problems += [f"missing {k}" for k in required if k not in check]
    problems += [f"unknown field {k}" for k in check if k not in schema["properties"]]
    if check.get("task_id") != task_id:
        problems.append(f"task_id {check.get('task_id')!r} is not the folder name {task_id}")
    if check.get("dataset") not in schema["properties"]["dataset"]["enum"]:
        problems.append(f"dataset {check.get('dataset')!r}")
    elif check["dataset"] != dataset_of(task_id):
        problems.append(f"dataset {check['dataset']} does not match the task id")
    if not isinstance(check.get("author"), str) or not check.get("author"):
        problems.append("author is empty")
    if check.get("inputs") != schema["properties"]["inputs"]["const"]:
        problems.append(f"inputs must be exactly {schema['properties']['inputs']['const']}")
    if not isinstance(check.get("command"), str) or not check.get("command", "").strip():
        problems.append("command is empty")
    files = check.get("files")
    if not isinstance(files, list) or not files or not all(isinstance(f, str) and f for f in files):
        problems.append("files must be a non-empty list of paths")
        files = []
    for f in files:
        if f.startswith("/") or ".." in f.split("/") or "\\" in f:
            problems.append(f"file {f!r} leaves the repo")
        elif not (folder / "files" / f).is_file():
            problems.append(f"file {f} has no files/{f}")
    listed = set(files)
    for path in (folder / "files").rglob("*") if (folder / "files").is_dir() else ():
        rel = path.relative_to(folder / "files").as_posix()
        if path.is_file() and rel not in listed:
            problems.append(f"files/{rel} is not listed in files")
    if "frozen_at" in check:
        try:
            datetime.fromisoformat(str(check["frozen_at"]).replace("Z", "+00:00"))
        except ValueError:
            problems.append(f"frozen_at {check['frozen_at']!r} is not a date-time")
    return problems


def cmd_check(a):
    bad = 0
    for task_id in a.task_ids:
        problems = validate(task_id, a.draft)
        bad += bool(problems)
        print(f"{task_id}: " + ("ok" if not problems else "; ".join(problems)))
    return 1 if bad else 0


def cmd_freeze(a):
    for task_id in a.task_ids:
        if validate(task_id, draft=True):
            raise ValueError(f"{task_id}: run check --draft first")
        path = ACCEPTANCE / task_id / "check.json"
        check = json.loads(path.read_text(encoding="utf-8"))
        if "frozen_at" in check:
            raise ValueError(f"{task_id}: already frozen at {check['frozen_at']}")
        check["frozen_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        path.write_text(json.dumps(check, indent=2) + "\n", encoding="utf-8")
        print(f"{task_id}: frozen_at {check['frozen_at']}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("prepare", help="copy the instruction and the start repo into a scratch folder")
    s.add_argument("task_id")
    s.add_argument("--out", help=f"scratch folder outside the repo (default {SCRATCH}/<task-id>)")
    s.set_defaults(run=cmd_prepare)
    s = sub.add_parser("check", help="validate runs/acceptance/<task-id>/")
    s.add_argument("task_ids", nargs="+")
    s.add_argument("--draft", action="store_true", help="accept a missing frozen_at")
    s.set_defaults(run=cmd_check)
    s = sub.add_parser("freeze", help="set frozen_at to now")
    s.add_argument("task_ids", nargs="+")
    s.set_defaults(run=cmd_freeze)
    a = p.parse_args(argv)
    try:
        return a.run(a) or 0
    except (ValueError, LookupError, OSError, RuntimeError, subprocess.CalledProcessError) as e:
        print(f"acceptance: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
