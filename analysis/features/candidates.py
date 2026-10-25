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


CANDIDATES = {
    "rereads": rereads,
    "reads_between_edits": reads_between_edits,
    "searches": lambda calls: sum(c["command_class"] == "search" for c in calls),
    "vcs_calls": lambda calls: sum(c["command_class"] == "vcs" for c in calls),
}
