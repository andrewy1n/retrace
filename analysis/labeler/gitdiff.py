"""Git helpers for comparing two snapshots. Every diff names commits, never the working tree."""

import subprocess


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def tree(repo, ref):
    return git(repo, "rev-parse", f"{ref}^{{tree}}").strip()


def changed_files(repo, a, b):
    """Paths whose content or mode differs between a and b."""
    return git(repo, "diff", "--name-only", "--no-renames", "-z", a, b).split("\0")[:-1]


def added_lines(repo, a, b):
    """Lines added from a to b. A binary file adds 0."""
    total = 0
    for row in git(repo, "diff", "--numstat", "--no-renames", "-z", a, b).split("\0"):
        added = row.split("\t", 1)[0]
        if added.isdigit():
            total += int(added)
    return total


def blobs(repo, ref):
    """Path -> blob id for every file at ref."""
    out = {}
    for row in git(repo, "ls-tree", "-r", "-z", ref).split("\0")[:-1]:
        meta, path = row.split("\t", 1)
        out[path] = meta.split()[2]
    return out
