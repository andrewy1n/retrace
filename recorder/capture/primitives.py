#!/usr/bin/env python3
"""Write runs/primitives/<session-id>.json for every recorded session.

  primitives.py --sessions DIR --out DIR

Each session directory holds the Droid transcript and settings.json under factory-sessions/*/ and a
meta.json. A primitive is a deterministic fact about one tool call. The files never hold command text
or tool output, only classes, counts, and repo paths.
"""
import argparse
import json
import os
import posixpath
import re
import sys
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(os.environ.get("RETRACE_REPO", Path(__file__).resolve().parents[2]))
CHECKOUTS = ("/testbed/", "/app/")
SESSION_ID = re.compile(r"^(?P<job>.+?)-(?P<task>instance_[\w.-]+?__[\w.-]+|[\w.-]+?__[\w.-]+?-\d+)-(?P<trial>\d+)$")
EXIT_LINE = re.compile(r"\[Process exited with code (-?\d+)\]\s*$")

TOOL_CLASS = {
    "Read": "read",
    "Grep": "search",
    "Glob": "search",
    "Edit": "edit",
    "MultiEdit": "edit",
    "Create": "edit",
    "ApplyPatch": "edit",
}
RANK = ["test", "install", "sleep_or_wait", "run", "vcs", "edit", "search", "read"]
SEARCH = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "find"}
READ = {"cat", "head", "tail", "ls", "wc", "nl", "less", "more", "sed", "awk", "diff", "stat", "file", "tree", "sort", "uniq", "cut", "tr", "xargs", "basename", "dirname", "realpath"}
EDIT = {"cp", "mv", "rm", "touch", "mkdir", "chmod", "tee", "ln", "truncate", "patch", "rmdir"}
NEUTRAL = {"cd", "source", ".", "export", "set", "unset", "true", "false", "echo", "printf", "pwd", ":", "exit", "return", "test", "[", "[[", "read", "alias", "ulimit"}
KEYWORDS = {"if", "then", "do", "else", "elif", "fi", "done", "while", "until", "!", "{", "}", "time", "exec", "command", "sudo", "env", "stdbuf", "xvfb-run"}
BACKGROUND_WRAPPERS = {"nohup", "setsid"}
VALUE_OPTIONS = {
    "-k", "-m", "-p", "-n", "-c", "-o", "-W", "-t", "--tb", "--maxfail", "--timeout", "--rootdir", "--junitxml",
    "--durations", "--deselect", "--ignore", "--settings", "--pattern", "--top-level-directory", "--start-at",
    "--start-after", "--testrunner", "--bisect", "--pair", "--tag", "--exclude-tag", "--split", "--seed",
    "-run", "-skip", "-tags", "-count", "-timeout", "-shuffle", "-parallel", "-cpu", "-bench", "-benchtime", "-mod",
    "-covermode", "-coverprofile", "-coverpkg", "-ldflags", "-gcflags", "-vet", "-exec",
    "--truncate", "--test", "--python", "--target-python", "--controller", "--target",
}
ANSIBLE_TEST_COMMANDS = {"units", "sanity", "integration", "network-integration", "windows-integration"}
OPTIONAL_NUMBER_OPTIONS = {"-v", "--verbosity", "--parallel"}
SYMPY_TEST_CALL = re.compile(r"\bsympy\.test\(([^)]*)\)")
KEYWORD_ARG = re.compile(r"\b\w+\s*=")
STRING_ARG = re.compile(r"""(['"])[^'"]+\1""")


def scan(text):
    """Split a shell command into simple commands: words, file redirects, and whether `&` ended it."""
    commands, words, redirects = [], [], []
    cur, quoted, pending, heredocs = "", False, None, []
    i, n = 0, len(text)

    def end_word():
        nonlocal cur, quoted, pending
        if cur or quoted:
            if pending == "<<":
                heredocs.append(cur)
            elif pending:
                redirects.append((pending, cur))
            else:
                words.append(cur)
            pending = None
        cur, quoted = "", False

    def end_command(background=False):
        nonlocal words, redirects
        end_word()
        if words or redirects:
            commands.append({"words": words, "redirects": redirects, "background": background})
        words, redirects = [], []

    while i < n:
        c = text[i]
        if c == "\\":
            if text[i + 1:i + 2] == "\n":
                i += 2
                continue
            cur += text[i + 1:i + 2]
            i += 2
        elif c == "'":
            j = text.find("'", i + 1)
            j = n if j < 0 else j
            cur, quoted, i = cur + text[i + 1:j], True, j + 1
        elif c == '"':
            j, buf = i + 1, ""
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    j += 1
                buf += text[j]
                j += 1
            cur, quoted, i = cur + buf, True, j + 1
        elif c == "$" and text[i + 1:i + 2] == "(":
            depth, j = 1, i + 2
            while j < n and depth:
                depth += (text[j] == "(") - (text[j] == ")")
                j += 1
            cur, i = cur + text[i:j], j
        elif c == "`":
            j = text.find("`", i + 1)
            j = n if j < 0 else j
            cur, i = cur + text[i:j + 1], j + 1
        elif c == "#" and not cur:
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif c in " \t":
            end_word()
            i += 1
        elif c == "\n":
            end_command()
            i += 1
            for delimiter in heredocs:
                lines = text[i:].split("\n")
                skip = next((k for k, line in enumerate(lines) if line.strip() == delimiter), len(lines) - 1)
                i += sum(len(line) + 1 for line in lines[:skip + 1])
            heredocs = []
        elif c in "<>" or (c == "&" and text[i + 1:i + 2] == ">"):
            if cur.isdigit():
                cur = ""
            m = re.match(r"&>>?|<<<|<<-?|>>|>&|>|<", text[i:])
            end_word()
            op = m.group(0)
            pending = "<<" if op.startswith("<<") and op != "<<<" else (">" if op in (">", ">>", "&>", "&>>") else "skip")
            i += len(op)
        elif text.startswith(("&&", "||"), i):
            end_command()
            i += 2
        elif c in ";|()":
            end_command()
            i += 1
        elif c == "&":
            end_command(background=True)
            i += 1
        else:
            cur += c
            i += 1
    end_command()
    return commands


def unwrap(words):
    """Return (program, args, wrapped_in_background) after env assignments, keywords, and wrappers."""
    words, wrapped = list(words), False
    while words:
        w = words[0]
        if re.match(r"^\w+=", w) or w in KEYWORDS:
            words = words[1:]
        elif w in BACKGROUND_WRAPPERS:
            wrapped = True
            words = words[1:]
        elif w == "timeout":
            words = words[1:]
            while words and (words[0].startswith("-") or re.match(r"^\d+[smhd]?$", words[0])):
                words = words[1:]
        elif w in ("for", "case", "select"):
            return None, [], wrapped
        else:
            break
    return (words[0], words[1:], wrapped) if words else (None, [], wrapped)


def positionals(args):
    out, i = [], 0
    while i < len(args):
        a = args[i]
        if a.startswith("-"):
            if a in VALUE_OPTIONS:
                i += 1
            elif a in OPTIONAL_NUMBER_OPTIONS and i + 1 < len(args) and args[i + 1].isdigit():
                i += 1
        else:
            out.append(a)
        i += 1
    return out


def runner_targets(runner, args):
    targets = positionals(args)
    if runner == "go_test":
        return [t.removeprefix("./") for t in targets if t != "./..."]
    return targets


def python_invocation(args):
    """Return (kind, runner, rest) for the arguments of a python interpreter call."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-m" and i + 1 < len(args):
            module = args[i + 1]
            if module == "pytest":
                return "test", "pytest", args[i + 2:]
            if module == "unittest":
                return "test", "unittest", args[i + 2:]
            return ("install" if module == "pip" and "install" in args else "run"), None, []
        if a == "-c" and i + 1 < len(args):
            call = SYMPY_TEST_CALL.search(args[i + 1])
            if call:
                positional = KEYWORD_ARG.split(call.group(1))[0]
                return "test", "sympy_bin_test", [m.group(0).strip("'\"") for m in STRING_ARG.finditer(positional)]
            return "run", None, []
        if a in ("-W", "-X"):
            i += 1
        elif not a.startswith("-") or a == "-":
            script = posixpath.basename(a)
            if script == "ansible-test":
                return ansible_test_invocation(args[i + 1:])
            if script == "runtests.py":
                return "test", "django_runtests", args[i + 1:]
            if a == "bin/test" or a.endswith("/bin/test"):
                return "test", "sympy_bin_test", args[i + 1:]
            return "run", None, []
        i += 1
    return "run", None, []


def ansible_test_invocation(args):
    for i, a in enumerate(args):
        if not a.startswith("-"):
            return ("test", "ansible_test", args[i + 1:]) if a in ANSIBLE_TEST_COMMANDS else ("run", None, [])
    return "run", None, []


def classify_simple(command):
    """Return (class, test_runner, test_args, backgrounded) for one simple command."""
    prog, args, wrapped = unwrap(command["words"])
    writes = any(op == ">" and target != "/dev/null" for op, target in command["redirects"])
    cls, runner, rest = None, None, []
    if prog is not None:
        base = posixpath.basename(prog)
        if re.fullmatch(r"python[\d.]*", base):
            cls, runner, rest = python_invocation(args)
        elif base in ("pytest", "py.test"):
            cls, runner, rest = "test", "pytest", args
        elif base == "go" and args[:1] == ["test"]:
            cls, runner, rest = "test", "go_test", args[1:]
        elif base == "ansible-test":
            cls, runner, rest = ansible_test_invocation(args)
        elif base == "runtests.py":
            cls, runner, rest = "test", "django_runtests", args
        elif prog == "bin/test" or prog.endswith("/bin/test"):
            cls, runner, rest = "test", "sympy_bin_test", args
        elif base in ("pip", "pip3", "conda", "apt", "apt-get") and "install" in args:
            cls = "install"
        elif base == "git":
            cls = "vcs"
        elif base in ("sleep", "wait"):
            cls = "sleep_or_wait"
        elif base == "tail" and any(a in ("-f", "-F", "--follow") for a in args):
            cls = "sleep_or_wait"
        elif base == "sed" and any(a == "-i" or a.startswith("-i") or a == "--in-place" for a in args if a.startswith("-")):
            cls = "edit"
        elif base in SEARCH:
            cls = "search"
        elif base in READ:
            cls = "read"
        elif base in EDIT:
            cls = "edit"
        elif base in ("bash", "sh", "zsh", "django-admin") or prog.startswith(("./", "/")):
            cls = "run"
        elif base not in NEUTRAL:
            cls = "other"
    if writes and cls in (None, "read", "other"):
        cls = "edit"
    return cls, runner, rest, wrapped or command["background"]


def classify_shell(command):
    classes, test, background = [], None, False
    for simple in scan(command):
        cls, runner, rest, bg = classify_simple(simple)
        background = background or bg
        if cls == "test" and test is None:
            test = (runner, rest)
        classes.append(cls)
    ranked = [c for c in classes if c in RANK]
    return (min(ranked, key=RANK.index) if ranked else "other"), test, background


def repo_path(path):
    for checkout in CHECKOUTS:
        if path == checkout.rstrip("/"):
            return "."
        if path.startswith(checkout):
            return path[len(checkout):]
    return path


def normalized_input(name, tool_input):
    if name == "Execute":
        return name, " ".join(tool_input.get("command", "").split())
    return name, json.dumps(tool_input, sort_keys=True)


def epoch(timestamp):
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()


def load_transcript(path):
    uses, turns, results, hooks = [], 0, {}, {}
    for line in Path(path).read_text().splitlines():
        row = json.loads(line)
        message = row.get("message") or {}
        if row.get("type") != "message":
            continue
        if message.get("hookEventName"):
            if message.get("hookToolCallId") and "hookStartTime" in message:
                hooks[message["hookToolCallId"]] = message["hookStartTime"] / 1000
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        if message.get("role") == "assistant":
            for block in content:
                if block.get("type") == "tool_use":
                    uses.append({"block": block, "turn": turns, "time": epoch(row["timestamp"])})
            turns += 1
        else:
            for block in content:
                if block.get("type") == "tool_result":
                    results[block["tool_use_id"]] = {"block": block, "time": epoch(row["timestamp"])}
    return uses, turns, results, hooks


def build_call(position, use, results, hooks, seen, assistant_turns):
    block, name = use["block"], use["block"]["name"]
    tool_input = block.get("input") or {}
    result = results.get(block["id"])
    output = result["block"]["content"] if result else None
    if not isinstance(output, str) and result:
        output = json.dumps(output)

    cls, runner, path_args, background, files = TOOL_CLASS.get(name), None, None, False, []
    if name == "Execute":
        cls, test, background = classify_shell(tool_input.get("command", ""))
        background = background or bool(tool_input.get("fireAndForget")) or bool(output and "Status: Running in background" in output)
        if test:
            runner, args = test
            targets = runner_targets(runner, args)
            path_args = len(targets)
            files = [repo_path(t) for t in targets if not re.search(r"[$`]", t)]
    else:
        cls = cls or "other"
        path = tool_input.get("file_path") or tool_input.get("path")
        files = [repo_path(path)] if isinstance(path, str) and path else []

    if result:
        end = hooks.get(block["id"], result["time"])
        duration = round(max(0.0, end - use["time"]), 3)
        match = EXIT_LINE.search(output) if name == "Execute" else None
        exit_code = int(match.group(1)) if match else None
        is_error = bool(result["block"].get("is_error"))
    else:
        duration = exit_code = is_error = None

    key = normalized_input(name, tool_input)
    repeats = key in seen
    seen.add(key)
    return {
        "tool_call_id": block["id"],
        "position": position,
        "turn": use["turn"],
        "tool_name": name,
        "command_class": cls,
        "test_runner": runner,
        "path_arg_count": path_args,
        "background": background,
        "duration_s": duration,
        "is_error": is_error,
        "exit_code": exit_code,
        "files": files,
        "output_chars": len(output) if output is not None else None,
        "output_tokens_est": len(output) // 4 if output is not None else None,
        "turns_after": assistant_turns - 1 - use["turn"],
        "repeats_earlier": repeats,
    }


def session_primitives(session_dir):
    session_dir = Path(session_dir)
    ids = SESSION_ID.match(session_dir.name)
    if not ids:
        sys.exit(f"{session_dir.name}: name is not <job-id>-<task-id>-<trial>")
    transcript = next(session_dir.glob("factory-sessions/*/*.jsonl"))
    settings = json.loads(transcript.with_suffix(".settings.json").read_text())["tokenUsage"]
    meta = json.loads((session_dir / "meta.json").read_text())
    uses, assistant_turns, results, hooks = load_transcript(transcript)
    seen = set()
    calls = [build_call(i, use, results, hooks, seen, assistant_turns) for i, use in enumerate(uses)]
    return {
        "session_id": session_dir.name,
        "task_id": ids["task"],
        "job_id": ids["job"],
        "trial": int(ids["trial"]),
        "harness": "droid",
        "assistant_turns": assistant_turns,
        "tool_calls": len(calls),
        "token_usage": {
            "input_tokens": settings["inputTokens"],
            "output_tokens": settings["outputTokens"],
            "cache_creation_tokens": settings["cacheCreationTokens"],
            "cache_read_tokens": settings["cacheReadTokens"],
            "thinking_tokens": settings["thinkingTokens"],
            "factory_credits": settings["factoryCredits"],
        },
        "timed_out": meta.get("droid_exit") == 124,
        "calls": calls,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", required=True)
    ap.add_argument("--out", default=REPO / "runs" / "primitives")
    args = ap.parse_args()

    schema = json.loads((REPO / "contracts" / "primitives.schema.json").read_text())
    validator = Draft202012Validator(schema)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for session_dir in sorted(Path(args.sessions).iterdir()):
        if not session_dir.is_dir() or session_dir.name.startswith("trace-check-"):
            continue
        primitives = session_primitives(session_dir)
        errors = sorted(validator.iter_errors(primitives), key=str)
        if errors:
            sys.exit(f"{session_dir.name}: primitives.schema.json: " + "; ".join(e.message for e in errors))
        (out / f"{session_dir.name}.json").write_text(json.dumps(primitives, indent=2) + "\n")
        print(f"{session_dir.name}: {primitives['tool_calls']} calls over {primitives['assistant_turns']} turns")


if __name__ == "__main__":
    main()
