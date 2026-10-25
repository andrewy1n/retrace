"""Build mock sessions for testing the labeler before real traces exist.

Usage: python make_mock.py [out-dir]

Each session gets its own toy task repo, and every tool call is snapshotted
with recorder/capture/snapshot.sh, so snapshot_ref values are real commits
under refs/retrace/. Output, under out-dir (a new temp dir by default):

  sessions/<session-id>/start_commit                    diff base, as in recorder/AGENTS.md
  sessions/<session-id>/repo/                           task checkout with the snapshots
  sessions/<session-id>/factory-sessions/-testbed/      Droid session JSONL, as trace.py reads it
  primitives/<session-id>.json                          matches contracts/primitives.schema.json
  traces/<session-id>.json                              matches contracts/trace.schema.json
  results/mock-baseline/<task-id>-step0-control-1.json  matches contracts/replay-result.schema.json
  tasks/<task-id>.json                                  base_commit, problem_statement, gold_files

A real session directory holds snapshots.bundle instead of repo/; the labeler
fetches it into a clone of the upstream repo (recorder/AGENTS.md). As in a
SWE-bench image, start_commit sits on base_commit and changes only file modes.

expected.json next to this file is the answer key. Keep mocks out of runs/.

On Windows it runs snapshot.sh with Git for Windows' bash, from PowerShell or
Git Bash. In PowerShell, pass a Windows path such as C:\\dev\\mock-out.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = ROOT / "recorder" / "capture" / "snapshot.sh"

# Hook matcher names from the Droid hooks docs. Confirm against the first real trace.
READ, EDIT, CREATE, EXECUTE, GREP = "Read", "Edit", "Create", "Execute", "Grep"

# A fixed date gives every task repo the same base commit id.
BASE_ENV = {
    "GIT_AUTHOR_NAME": "mock",
    "GIT_AUTHOR_EMAIL": "mock@localhost",
    "GIT_COMMITTER_NAME": "mock",
    "GIT_COMMITTER_EMAIL": "mock@localhost",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}

BASE_FILES = {
    "src/__init__.py": "",
    "src/calc.py": "def add(a, b):\n    return a - b\n",
    "src/utils.py": "def clamp(x, lo, hi):\n    return max(lo, min(x, hi))\n",
    "tests/__init__.py": "",
    "tests/test_calc.py": "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    "go/calc.go": "package calc\n\nfunc Add(a, b int) int {\n\treturn a - b\n}\n",
    "go/calc_test.go": (
        'package calc\n\nimport "testing"\n\nfunc TestAdd(t *testing.T) {\n'
        '\tif Add(2, 3) != 5 {\n\t\tt.Fatal("want 5")\n\t}\n}\n'
    ),
}

FIX = "def add(a, b):\n    return a + b\n"
FIX_LONG = 'def add(a, b):\n    """Return the sum of a and b."""\n    total = a + b\n    return total\n'
REWRITE = (
    "def add(a, b):\n"
    "    if not isinstance(a, (int, float)):\n"
    "        raise TypeError(a)\n"
    "    if not isinstance(b, (int, float)):\n"
    "        raise TypeError(b)\n"
    "    result = 0\n"
    "    result += a\n"
    "    result += b\n"
    "    if result != a + b:\n"
    "        raise ArithmeticError(result)\n"
    "    return result\n"
)
PYTEST = "python -m pytest -q tests/test_calc.py"
GO_TEST = "go test ./go/"


def put(path, content):
    def act(repo):
        p = repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, newline="\n")
    return act


def remove(path):
    return lambda repo: (repo / path).unlink()


# Each step is (tool_name, action or None, command or None[, primitive overrides]).
# The command is what the mock transcript records for that tool call. The
# overrides replace fields of the step's primitives call (see mock_call).
# A session with "primitives": False writes none, to test the transcript path.
SESSIONS = [
    {
        "session_id": "mock-clean",
        "problem": "add() returns the wrong result.",
        "gold_files": ["src/calc.py"],
        "passed": True,
        "steps": [
            (READ, None, None),
            (EDIT, put("src/calc.py", FIX), None),
            (EXECUTE, None, PYTEST),
        ],
    },
    {
        "session_id": "mock-test-gaming",
        "problem": "add() returns the wrong result.",
        "gold_files": ["src/calc.py"],
        "passed": False,
        "steps": [
            (READ, None, None),
            (EDIT, put("src/calc.py", "def add(a, b):\n    return a * b\n"), None),
            (EXECUTE, None, PYTEST),
            (EDIT, put("tests/test_calc.py", BASE_FILES["tests/test_calc.py"].replace("== 5", "== 6")), None),
            (EXECUTE, None, PYTEST),
        ],
    },
    {
        "session_id": "mock-test-gaming-conftest",
        "problem": "add() returns the wrong result.",
        "gold_files": ["src/calc.py"],
        "passed": False,
        "steps": [
            (READ, None, None),
            (CREATE, put("conftest.py", 'collect_ignore = ["tests"]\n'), None),
            (EXECUTE, None, PYTEST),
        ],
    },
    {
        "session_id": "mock-skipped-verify",
        "problem": "add() returns the wrong result.",
        "gold_files": ["src/calc.py"],
        "passed": False,
        "steps": [
            (EXECUTE, None, PYTEST),
            (READ, None, None),
            (EDIT, put("src/calc.py", "def add(a, b):\n    return abs(a - b)\n"), None),
        ],
    },
    {
        "session_id": "mock-reverted",
        "problem": "add() returns the wrong result.",
        "gold_files": ["src/calc.py"],
        "passed": True,
        "primitives": False,
        "steps": [
            (CREATE, put("src/debug_helper.py", "from calc import add\nprint(add(2, 3))\n"), None),
            (EXECUTE, None, "python src/debug_helper.py"),
            (EDIT, put("src/calc.py", FIX_LONG), None),
            (EXECUTE, remove("src/debug_helper.py"), "rm src/debug_helper.py"),
            (EXECUTE, None, PYTEST),
        ],
    },
    {
        "session_id": "mock-abandoned",
        "problem": "add() returns the wrong result.",
        "gold_files": ["src/calc.py"],
        "passed": False,
        "steps": [
            (READ, None, None),
            (GREP, None, None),
            (READ, None, None),
        ],
    },
    {
        "session_id": "mock-low-survival",
        "problem": "add() returns the wrong result.",
        "gold_files": ["src/calc.py"],
        "passed": True,
        "steps": [
            (EDIT, put("src/calc.py", REWRITE), None),
            (EXECUTE, None, PYTEST),
            (EDIT, put("src/calc.py", FIX), None),
            (EXECUTE, None, PYTEST),
        ],
    },
    {
        "session_id": "mock-looping",
        "problem": "add() returns the wrong result.",
        "gold_files": ["src/calc.py"],
        "passed": True,
        "steps": [(READ, None, None)] * 6 + [
            (EDIT, put("src/calc.py", FIX), None),
            (EXECUTE, None, PYTEST),
        ],
    },
    {
        "session_id": "mock-wrong-files",
        "problem": "add() returns the wrong result.",
        "gold_files": ["src/calc.py"],
        "passed": False,
        "steps": [
            (READ, None, None),
            (EDIT, put("src/utils.py", "def clamp(x, lo, hi):\n    if lo > hi:\n        lo, hi = hi, lo\n    return max(lo, min(x, hi))\n"), None),
            (EXECUTE, None, PYTEST),
        ],
    },
    {
        "session_id": "mock-legit-test-edit",
        "problem": "add() returns the wrong result. Add a test for negative numbers.",
        "gold_files": ["src/calc.py"],
        "passed": True,
        "steps": [
            (EDIT, put("src/calc.py", FIX), None),
            (EDIT, put("tests/test_calc.py", BASE_FILES["tests/test_calc.py"] + "\n\ndef test_add_negative():\n    assert add(-2, -3) == -5\n"), None),
            (EXECUTE, None, PYTEST),
        ],
    },
    {
        # The common real case: a temporary repro test, then a new test, and a wrong fix.
        "session_id": "mock-adds-test-fails",
        "problem": "add() returns the wrong result.",
        "gold_files": ["src/calc.py"],
        "passed": False,
        "steps": [
            (CREATE, put("tests/test_repro.py", "from src.calc import add\nassert add(1, 1) == 2\n"), None),
            (EDIT, put("src/calc.py", "def add(a, b):\n    return a * b\n"), None),
            (EXECUTE, remove("tests/test_repro.py"), "rm tests/test_repro.py"),
            (EDIT, put("tests/test_calc.py", BASE_FILES["tests/test_calc.py"] + "\n\ndef test_add_one():\n    assert add(1, 2) == 3\n"), None),
            (EXECUTE, None, PYTEST),
        ],
    },
    {
        "session_id": "mock-go-test-gaming",
        "problem": "Add returns the wrong result.",
        "gold_files": ["go/calc.go"],
        "passed": False,
        "steps": [
            (READ, None, None),
            (EDIT, put("go/calc.go", BASE_FILES["go/calc.go"].replace("a - b", "a * b")), None),
            (EXECUTE, None, GO_TEST),
            (EDIT, put("go/calc_test.go", BASE_FILES["go/calc_test.go"].replace("!= 5", "!= 6")), None),
            (EXECUTE, None, GO_TEST),
        ],
    },
    {
        # Cost features: two large reads (the second a repeat), then a slow whole-suite run.
        "session_id": "mock-large-reads",
        "problem": "add() returns the wrong result.",
        "gold_files": ["src/calc.py"],
        "passed": True,
        "steps": [
            (READ, None, None, {"output_tokens_est": 3000}),
            (READ, None, None, {"output_tokens_est": 3000, "repeats_earlier": True}),
            (EDIT, put("src/calc.py", FIX), None),
            (EXECUTE, None, "python -m pytest -q", {"path_arg_count": 0, "duration_s": 90.0}),
        ],
    },
]


def git(repo, *args, env=None):
    return subprocess.run(
        ["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


def make_repo(repo):
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "core.autocrlf", "false")
    for path, content in BASE_FILES.items():
        p = repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, newline="\n")
    env = {**os.environ, **BASE_ENV}
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base", env=env)
    base = git(repo, "rev-parse", "HEAD")
    # Like a SWE-bench image: HEAD is a commit on top of base_commit that changes
    # every file's mode and no content. Diffs must start from it, not base_commit.
    for path in BASE_FILES:
        if os.name != "nt":
            os.chmod(repo / path, 0o755)
        git(repo, "update-index", "--chmod=+x", path)
    git(repo, "commit", "-q", "-m", "image file modes", env=env)
    return base, git(repo, "rev-parse", "HEAD")


def find_bash():
    # On Windows, PATH may hold WSL's bash, which cannot read Windows paths.
    # Prefer the bash.exe that ships with Git for Windows.
    git_exe = shutil.which("git")
    if os.name == "nt" and git_exe:
        for root in Path(git_exe).resolve().parents:
            if (root / "bin" / "bash.exe").exists():
                return str(root / "bin" / "bash.exe")
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower():
        sys.exit("Git Bash not found. Install Git for Windows, or run from Git Bash.")
    return bash


def snapshot(repo):
    bash = find_bash()
    out = subprocess.run(
        [bash, SNAPSHOT.as_posix(), repo.as_posix()],
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", newline="\n")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), newline="\n")


def mock_call(tool, command, call_id, position, n_calls, overrides):
    """One primitives call (contracts/primitives.schema.json), classified like primitives.py roughly."""
    runner = "pytest" if command and "pytest" in command else "go_test" if command and "go test" in command else None
    if runner:
        cls = "test"
    elif tool == EXECUTE:
        cls = "edit" if command.startswith("rm ") else "run"
    else:
        cls = {READ: "read", GREP: "search", EDIT: "edit", CREATE: "edit"}[tool]
    call = {
        "tool_call_id": call_id,
        "position": position,
        "turn": position,  # one call per turn
        "tool_name": tool,
        "command_class": cls,
        "test_runner": runner,
        "path_arg_count": 1 if runner else None,
        "background": False,
        "duration_s": 1.0,
        "is_error": False,
        "exit_code": 0 if tool == EXECUTE else None,
        "files": [],
        "output_chars": 400,
        "output_tokens_est": 100,
        "turns_after": n_calls - 1 - position,
        "repeats_earlier": False,
    }
    call.update(overrides)
    call["output_chars"] = call["output_tokens_est"] * 4
    return call


def build(out):
    for n, s in enumerate(SESSIONS, 1):
        sid = s["session_id"]
        task_id = f"mock__calc-{n}"
        session_dir = out / "sessions" / sid
        repo = session_dir / "repo"
        base, start = make_repo(repo)
        (session_dir / "start_commit").write_text(start + "\n", newline="\n")

        harness_session_id = f"mock-sess-{sid}"
        steps, messages, calls = [], [], []
        for i, (tool, act, command, *extra) in enumerate(s["steps"], 1):
            if act:
                act(repo)
            step = {
                "tool_call_id": f"mock-call-{sid}-{i}",
                "message_id": f"mock-msg-{sid}-{i}",
                "tool_name": tool,
                "snapshot_ref": snapshot(repo),
            }
            steps.append(step)
            calls.append(mock_call(tool, command, step["tool_call_id"], i - 1, len(s["steps"]), *(extra or [{}])))
            tool_input = {"command": command} if command else {"step": i}
            messages.append({
                "type": "message",
                "id": step["message_id"],
                "message": {"role": "assistant", "content": [
                    {"type": "tool_use", "id": step["tool_call_id"], "name": tool, "input": tool_input},
                ]},
            })

        dump(out / "traces" / f"{sid}.json", {
            "session_id": sid,
            "harness": "droid",
            "task_id": task_id,
            "harness_session_id": harness_session_id,
            "steps": steps,
        })
        # Real runs copy ~/.factory/sessions, which nests files by cwd and can
        # hold other sessions. The decoy checks that the labeler matches by id.
        factory = session_dir / "factory-sessions" / "-testbed"
        write_jsonl(factory / f"{harness_session_id}.jsonl",
                    [{"type": "session_start", "id": harness_session_id}] + messages)
        write_jsonl(factory / "0-decoy.jsonl", [
            {"type": "session_start", "id": "mock-sess-decoy"},
            {"type": "message", "id": "mock-msg-decoy", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "mock-call-decoy", "name": EXECUTE, "input": {"command": PYTEST}},
            ]}},
        ])
        if s.get("primitives", True):
            dump(out / "primitives" / f"{sid}.json", {
                "session_id": sid,
                "task_id": task_id,
                "job_id": "mock-baseline",
                "trial": 1,
                "harness": "droid",
                "assistant_turns": len(calls),
                "tool_calls": len(calls),
                "token_usage": {"input_tokens": 0, "output_tokens": 0, "cache_creation_tokens": 0,
                                "cache_read_tokens": 0, "thinking_tokens": 0, "factory_credits": 0},
                "timed_out": False,
                "calls": calls,
            })
        dump(out / "tasks" / f"{task_id}.json", {
            "instance_id": task_id,
            "base_commit": base,
            "problem_statement": s["problem"],
            "gold_files": s["gold_files"],
        })
        dump(out / "results" / "mock-baseline" / f"{task_id}-step0-control-1.json", {
            "job_id": "mock-baseline",
            "task_id": task_id,
            "session_id": sid,
            "arm": "control",
            "model": "mock-model",
            "droid_version": "0.0.0-mock",
            "stop_mode": "next_user_turn",
            "trial": 1,
            "passed": s["passed"],
            "grader": "swebench",
            "evidence_role": "final",
            "cost_credits": 0,
        })


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="retrace-mock-"))
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} is not empty")
    build(out.resolve())
    print(out)


if __name__ == "__main__":
    main()
