"""Cost features of one session, from its primitives (contracts/primitives.schema.json).

Each feature is a count or a sum over the session's calls. A feature is present
when its value is above 0. Definitions are in analysis/AGENTS.md. Primitives
hold no command text and no tool output, so features need no private data.
"""

# Starting values, to be checked against the baseline.
LARGE_OUTPUT_TOKENS = 2000
SLOW_TEST_S = 60


def large(c):
    return (c["output_tokens_est"] or 0) > LARGE_OUTPUT_TOKENS


def whole_suite(c):
    return c["command_class"] == "test" and c["path_arg_count"] == 0


def calls_before_first_edit(calls):
    edits = [c["position"] for c in calls if c["command_class"] == "edit"]
    return min(edits) if edits else len(calls)


def shell_error_streak(calls):
    prev, n = None, 0
    for c in calls:
        if c["tool_name"] == "Execute":
            n += bool(c["is_error"] and prev is not None and prev["is_error"])
            prev = c
    return n


def large_root_searches(calls):
    return sum(c["command_class"] == "search" and c["files"] == ["."] and large(c) for c in calls)


def file_rereads(calls):
    seen, n = set(), 0
    for c in calls:
        if c["tool_name"] == "Read" and c["files"]:
            n += c["files"][0] in seen
            seen.add(c["files"][0])
    return n


def calls_after_last_edit(calls):
    edits = [c["position"] for c in calls if c["command_class"] == "edit"]
    return sum(c["position"] > max(edits) for c in calls) if edits else 0


FEATURES = {
    "large_outputs": lambda calls: sum(large(c) for c in calls),
    "large_reads": lambda calls: sum(large(c) for c in calls if c["tool_name"] == "Read"),
    "carried_output_tokens": lambda calls: sum((c["output_tokens_est"] or 0) * c["turns_after"] for c in calls),
    "repeated_calls": lambda calls: sum(c["repeats_earlier"] for c in calls),
    "whole_suite_tests": lambda calls: sum(whole_suite(c) for c in calls),
    "slow_whole_suite_tests": lambda calls: sum(whole_suite(c) and (c["duration_s"] or 0) > SLOW_TEST_S for c in calls),
    "tool_errors": lambda calls: sum(bool(c["is_error"]) for c in calls),
    "calls_after_last_edit": calls_after_last_edit,
    "calls_before_first_edit": calls_before_first_edit,
    "shell_error_streak": shell_error_streak,
    "large_root_searches": large_root_searches,
    "file_rereads": file_rereads,
}

SHELL_ERROR_STREAK_MIN = 3
LARGE_ROOT_SEARCHES_MIN = 1
FILE_REREADS_MIN = 3


def shell_error_streak_signal(calls):
    """(holds, count): 3 or more errored Execute calls that each follow an errored Execute call."""
    n = shell_error_streak(calls)
    return n >= SHELL_ERROR_STREAK_MIN, n


def large_root_searches_signal(calls):
    """(holds, count): a search over the whole repo returns over 2,000 tokens at least once."""
    n = large_root_searches(calls)
    return n >= LARGE_ROOT_SEARCHES_MIN, n


def file_rereads_signal(calls):
    """(holds, count): 3 or more Read calls of a file that an earlier Read call read."""
    n = file_rereads(calls)
    return n >= FILE_REREADS_MIN, n


def features(primitives):
    """Feature name -> value, or None for a session without primitives."""
    if primitives is None:
        return None
    return {name: f(primitives["calls"]) for name, f in FEATURES.items()}
