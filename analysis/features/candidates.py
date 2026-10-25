"""Candidate features from discovery round 1, not yet promoted.

Found by comparing the longer and shorter control run of each derivation task
(21 pairs, primitives only). The 127 extra calls in the longer runs were mostly
Read calls (72), made between the first and last edit (80), and 29 of them re-read
a file the session had already read. Errors, failing tests, and re-edits explained
almost none. score.py validates these. A candidate joins FEATURES in features.py
only once it is promoted. calls_before_first_edit was promoted (16% out of task)
and is the Gate 3 target.

Scores in round 1 (out of task): vcs_calls 25%, searches 17%, rereads -9%,
reads_between_edits -1%.

Round 2 added reads_after_edit (-5%), edit_only_turns (-19%), and test_reruns (+2%)
on the same 43 sessions, and promoted shell_error_streak and large_root_searches by
count times cost (analysis/AGENTS.md).
"""


def edit_span(calls):
    edits = [c["position"] for c in calls if c["command_class"] == "edit"]
    return (min(edits), max(edits)) if edits else (None, None)


def rereads(calls):
    """Read calls whose files were all read earlier, even with other arguments."""
    seen, n = set(), 0
    for c in calls:
        if c["command_class"] == "read" and c["files"]:
            n += all(f in seen for f in c["files"])
            seen.update(c["files"])
    return n


def reads_between_edits(calls):
    first, last = edit_span(calls)
    return 0 if first is None else sum(c["command_class"] == "read" and first < c["position"] < last for c in calls)


def reads_after_edit(calls):
    """Read calls whose files were all edited earlier in the session."""
    edited, n = set(), 0
    for c in calls:
        if c["command_class"] == "read" and c["files"]:
            n += all(f in edited for f in c["files"])
        if c["command_class"] == "edit":
            edited.update(c["files"])
    return n


def edit_only_turns(calls):
    """Turns with only edit calls that follow a turn with only edit calls."""
    turns = {}
    for c in calls:
        turns.setdefault(c["turn"], []).append(c["command_class"] == "edit")
    order = sorted(turns)
    return sum(all(turns[t]) and all(turns[s]) for s, t in zip(order, order[1:]))


def test_reruns(calls):
    """Test calls with no edit since the previous test call."""
    n, tested, edited = 0, False, False
    for c in calls:
        if c["command_class"] == "edit":
            edited = True
        elif c["command_class"] == "test":
            n += tested and not edited
            tested, edited = True, False
    return n


CANDIDATES = {
    "rereads": rereads,
    "reads_between_edits": reads_between_edits,
    "searches": lambda calls: sum(c["command_class"] == "search" for c in calls),
    "vcs_calls": lambda calls: sum(c["command_class"] == "vcs" for c in calls),
    "reads_after_edit": reads_after_edit,
    "edit_only_turns": edit_only_turns,
    "test_reruns": test_reruns,
}
