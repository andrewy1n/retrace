#!/usr/bin/env python3
"""Pure logic behind proxies.sh: the repo-test and acceptance proxies of one trial's patch.

  repo_tests.py select --patch PATCH --tree TREE
  repo_tests.py parse [--junit FILE]... [--go FILE]...
  repo_tests.py compare START.json PATCHED.json
  repo_tests.py report --selection SEL.json [--start START.json --patched PATCHED.json] [--seconds N] [--error]
  repo_tests.py check CHECK.json
  repo_tests.py acceptance --sha SHA --at-start STATUS --status STATUS [--seconds N]
  repo_tests.py merge --repo-tests FILE [--acceptance FILE]

TREE lists the repo paths at the start commit, one per line. Every subcommand prints JSON on stdout.
A failure prints one line on stderr and exits 1. The output of `merge` is the `proxies` object of a replay result.
Standard library only.
"""
import argparse
import codecs
import hashlib
import json
import posixpath
import sys
import xml.etree.ElementTree as ET

PYTHON_CAP = 10
GO_CAP = 5
SEVERITY = {"pass": 0, "skip": 1, "fail": 2, "error": 3}
STATUSES = ("pass", "fail", "error")


def unquote(token):
    if len(token) >= 2 and token[0] == token[-1] == '"':
        raw = codecs.decode(token[1:-1], "unicode_escape")
        try:
            return raw.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return raw
    return token


def header_path(text, strip_prefix):
    token = unquote(text.split("\t")[0].rstrip())
    if token == "/dev/null":
        return None
    if strip_prefix and token[:2] in ("a/", "b/"):
        return token[2:]
    return token


def edited_paths(patch):
    paths = []
    in_header = True
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            in_header = True
        elif line.startswith("@@"):
            in_header = False
        elif in_header:
            for prefix, strip in (("--- ", True), ("+++ ", True), ("rename from ", False), ("rename to ", False)):
                if line.startswith(prefix):
                    path = header_path(line[len(prefix):], strip)
                    if path and path not in paths:
                        paths.append(path)
    return paths


def is_test_file(path):
    parts = path.split("/")
    name = parts[-1]
    if "tests" in parts[:-1] or "testing" in parts[:-1] or name == "conftest.py":
        return True
    if name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py")):
        return True
    return name.endswith("_test.go")


def shared_prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def dir_parts(path):
    d = posixpath.dirname(path)
    return d.split("/") if d else []


def select_python(sources, tree):
    by_name = {}
    for path in tree:
        by_name.setdefault(posixpath.basename(path), set()).add(path)
    ranked = []
    for src in sources:
        stem = posixpath.basename(src)[:-3]
        found = by_name.get(f"test_{stem}.py", set()) | by_name.get(f"{stem}_test.py", set())
        here = dir_parts(src)
        ranked.append(sorted(found, key=lambda c: (-shared_prefix(here, dir_parts(c)), c)))
    chosen = []
    for rank in range(max((len(r) for r in ranked), default=0)):
        for candidates in ranked:
            if rank < len(candidates) and candidates[rank] not in chosen:
                chosen.append(candidates[rank])
                if len(chosen) == PYTHON_CAP:
                    return chosen
    return chosen


def package_dir(path):
    return posixpath.dirname(path) or "."


def module_of(directory, module_dirs):
    parts = [] if directory == "." else directory.split("/")
    for n in range(len(parts), 0, -1):
        candidate = "/".join(parts[:n])
        if candidate in module_dirs:
            return candidate
    return "."


def select_go(sources, tree):
    test_dirs = {package_dir(p) for p in tree if p.endswith("_test.go")}
    dirs = []
    for src in sources:
        d = package_dir(src)
        if d in test_dirs and d not in dirs:
            dirs.append(d)
            if len(dirs) == GO_CAP:
                break
    module_dirs = {package_dir(p) for p in tree if posixpath.basename(p) == "go.mod"}
    runs = {}
    for d in dirs:
        module = module_of(d, module_dirs)
        rel = posixpath.relpath(d, module)
        runs.setdefault(module, []).append("." if rel == "." else f"./{rel}")
    restore = sorted(p for p in tree if p.endswith("_test.go") and package_dir(p) in dirs)
    return dirs, [{"module": m, "pkgs": pkgs} for m, pkgs in runs.items()], restore


def select(edited, tree):
    sources = [p for p in edited if not is_test_file(p)]
    python = select_python([p for p in sources if p.endswith(".py")], tree)
    go_dirs, go_runs, go_restore = select_go([p for p in sources if p.endswith(".go")], tree)
    selected = python + go_dirs
    key = hashlib.sha256("\n".join(sorted(selected)).encode()).hexdigest()
    return {"selected": selected, "key": key, "python": python, "go_dirs": go_dirs, "go_runs": go_runs,
            "restore": python + go_restore}


def merge_outcomes(into, tests):
    for test_id, outcome in tests.items():
        current = into.get(test_id)
        if current is None or SEVERITY[outcome] > SEVERITY[current]:
            into[test_id] = outcome


def parse_junit(text):
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ValueError(f"junit XML does not parse: {e}")
    tests = {}
    for case in root.iter("testcase"):
        tags = {child.tag for child in case}
        outcome = "error" if "error" in tags else "fail" if "failure" in tags else "skip" if "skipped" in tags else "pass"
        merge_outcomes(tests, {f"{case.get('classname', '')}::{case.get('name', '')}": outcome})
    return tests


def parse_gotest(text):
    events = 0
    state = {}
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        events += 1
        test = event.get("Test")
        if not test:
            continue
        test_id = f"{event.get('Package', '')}::{test}"
        action = event.get("Action")
        if action == "run":
            state.setdefault(test_id, "error")
        elif action in ("pass", "fail", "skip"):
            state[test_id] = action
    if not events:
        raise ValueError("go test output has no JSON events")
    return state


def compare(start, patched):
    passing = [t for t, o in start.items() if o == "pass"]
    return {
        "passing_at_start": len(passing),
        "regressed": sum(1 for t in passing if patched.get(t) in (None, "fail", "error")),
        "newly_passing": sum(1 for t, o in patched.items() if o == "pass" and start.get(t) != "pass"),
    }


def repo_tests_object(selection, start=None, patched=None, seconds=None, error=False):
    selected = selection["selected"]
    if not selected:
        return {"status": "no_tests", "selected": []}
    out = {"status": "error", "selected": selected}
    if not error and start is not None and patched is not None:
        out = {"status": "ok", "selected": selected, **compare(start, patched)}
    if seconds is not None:
        out["seconds"] = round(seconds, 1)
    return out


def load_check(raw):
    if isinstance(raw, str):
        raw = raw.encode()
    try:
        check = json.loads(raw)
    except ValueError as e:
        raise ValueError(f"check.json does not parse: {e}")
    if not isinstance(check, dict):
        raise ValueError("check.json is not an object")
    files, command = check.get("files"), check.get("command")
    if not isinstance(files, list) or not files or not all(isinstance(f, str) and f for f in files):
        raise ValueError("check.json needs a non-empty list of file paths")
    for f in files:
        if f.startswith("/") or ".." in f.split("/"):
            raise ValueError(f"check.json file path {f!r} leaves the repo")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("check.json needs a command")
    return {"files": files, "command": command, "sha256": hashlib.sha256(raw).hexdigest()}


def acceptance_object(sha, at_start, status, seconds=None):
    out = {"status": status, "at_start": at_start, "check_sha256": sha}
    if seconds is not None:
        out["seconds"] = round(seconds, 1)
    return out


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def read_json(path):
    return json.loads(read(path))


def emit(obj):
    json.dump(obj, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")


def cmd_select(a):
    tree = [line.strip() for line in read(a.tree).splitlines() if line.strip()]
    emit(select(edited_paths(read(a.patch)), tree))


def cmd_parse(a):
    tests = {}
    for path in a.junit:
        merge_outcomes(tests, parse_junit(read(path)))
    for path in a.go:
        merge_outcomes(tests, parse_gotest(read(path)))
    emit(tests)


def cmd_compare(a):
    emit(compare(read_json(a.start), read_json(a.patched)))


def cmd_report(a):
    start = read_json(a.start) if a.start else None
    patched = read_json(a.patched) if a.patched else None
    emit(repo_tests_object(read_json(a.selection), start, patched, a.seconds, a.error))


def cmd_check(a):
    with open(a.check, "rb") as f:
        emit(load_check(f.read()))


def cmd_acceptance(a):
    emit(acceptance_object(a.sha, a.at_start, a.status, a.seconds))


def cmd_merge(a):
    out = {"repo_tests": read_json(a.repo_tests)}
    if a.acceptance:
        out["acceptance"] = read_json(a.acceptance)
    emit(out)


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("select")
    s.add_argument("--patch", required=True)
    s.add_argument("--tree", required=True)
    s.set_defaults(run=cmd_select)

    s = sub.add_parser("parse")
    s.add_argument("--junit", action="append", default=[])
    s.add_argument("--go", action="append", default=[])
    s.set_defaults(run=cmd_parse)

    s = sub.add_parser("compare")
    s.add_argument("start")
    s.add_argument("patched")
    s.set_defaults(run=cmd_compare)

    s = sub.add_parser("report")
    s.add_argument("--selection", required=True)
    s.add_argument("--start")
    s.add_argument("--patched")
    s.add_argument("--seconds", type=float)
    s.add_argument("--error", action="store_true")
    s.set_defaults(run=cmd_report)

    s = sub.add_parser("check")
    s.add_argument("check")
    s.set_defaults(run=cmd_check)

    s = sub.add_parser("acceptance")
    s.add_argument("--sha", required=True)
    s.add_argument("--at-start", required=True, choices=STATUSES)
    s.add_argument("--status", required=True, choices=STATUSES)
    s.add_argument("--seconds", type=float)
    s.set_defaults(run=cmd_acceptance)

    s = sub.add_parser("merge")
    s.add_argument("--repo-tests", required=True)
    s.add_argument("--acceptance")
    s.set_defaults(run=cmd_merge)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.run(args)
    except (ValueError, OSError) as e:
        print(f"repo_tests: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
