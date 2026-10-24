"""The label rules in analysis/AGENTS.md: six hard signals, then failure type and suspected step."""

import re
from dataclasses import dataclass

from gitdiff import added_lines, blobs, changed_files, tree
from session import EXECUTE

# The pattern in reports/preregistration.md.
TEST_FILE = re.compile(r"(^|/)(test_[^/]*\.py|[^/]*_test\.py|conftest\.py)$|(^|/)(tests|testing)/")
# A starting list, to be checked against the baseline.
TEST_COMMAND = re.compile(r"\bpytest\b|\bunittest\b|\btox\b|manage\.py\s+test\b|runtests")
# Starting values, to be checked against the baseline.
SURVIVAL_MIN = 0.5
LOOP_MIN = 5


@dataclass
class Facts:
    """What the rules read, computed once per session. refs[0] is the start commit."""
    refs: list
    trees: list
    step_files: list  # files each step changed, one list per step
    step_added: int  # added lines summed over the step diffs
    final_files: list
    final_added: int


def facts(s):
    repo = s.repo
    refs = [s.start_commit] + [step["snapshot_ref"] for step in s.trace["steps"]]
    pairs = list(zip(refs, refs[1:]))
    return Facts(
        refs=refs,
        trees=[tree(repo, r) for r in refs],
        step_files=[changed_files(repo, a, b) for a, b in pairs],
        step_added=sum(added_lines(repo, a, b) for a, b in pairs),
        final_files=changed_files(repo, refs[0], refs[-1]),
        final_added=added_lines(repo, refs[0], refs[-1]),
    )


def is_test(path):
    return bool(TEST_FILE.search(path))


def failing_tests(s, f):
    return not s.result["passed"]


def reverted_diff(s, f):
    snaps = [blobs(s.repo, r) for r in f.refs]
    for path in set().union(*snaps):
        seen = []
        for snap in snaps:
            blob = snap.get(path)  # None while the file does not exist
            if not seen or seen[-1] != blob:
                if blob in seen:
                    return True
                seen.append(blob)
    return False


def abandoned(s, f):
    return not s.result["passed"] and not f.final_files


def code_survival(s, f):
    return f.step_added > 0 and f.final_added / f.step_added < SURVIVAL_MIN


def looping(s, f):
    run, prev = 0, None
    for i, step in enumerate(s.trace["steps"]):
        if f.trees[i] == f.trees[i + 1]:
            run = run + 1 if step["tool_name"] == prev else 1
            prev = step["tool_name"]
        else:
            run, prev = 0, None
        if run >= LOOP_MIN:
            return True
    return False


def wrong_files(s, f):
    edits_source = any(not is_test(p) for p in f.final_files)
    return edits_source and not set(f.final_files) & set(s.gold_files)


SIGNALS = {
    "failing_tests": failing_tests,
    "reverted_diff": reverted_diff,
    "abandoned": abandoned,
    "code_survival": code_survival,
    "looping": looping,
    "wrong_files": wrong_files,
}


def failure(s, f):
    """(failure_type, suspected_tool_call_id), by the ordered rules in analysis/AGENTS.md."""
    steps = s.trace["steps"]
    failed = not s.result["passed"]

    test_edits = [i for i, files in enumerate(f.step_files) if any(is_test(p) for p in files)]
    if test_edits and failed:
        return "test_gaming", steps[test_edits[0]]["tool_call_id"]

    source_edits = [i for i, files in enumerate(f.step_files) if any(not is_test(p) for p in files)]
    if source_edits:
        last = source_edits[-1]
        tested = any(
            step["tool_name"] == EXECUTE and TEST_COMMAND.search(s.commands.get(step["tool_call_id"], ""))
            for step in steps[last + 1:]
        )
        if not tested:
            return "skipped_verification", steps[last]["tool_call_id"]

    if failed:
        return "other", None  # until the Signals-style detector exists
    return None, None


def label(s):
    f = facts(s)
    failure_type, suspected = failure(s, f)
    return {
        "session_id": s.session_id,
        "hard_signals": [name for name, rule in SIGNALS.items() if rule(s, f)],
        "failure_type": failure_type,
        "suspected_tool_call_id": suspected,
    }
