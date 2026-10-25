I'm proposing one change: a `PostToolUse` hook that sets an exploration budget. It counts read-only tool calls (reads, searches, listings and shell commands) until the first file edit. After 10 such calls it tells the agent to commit to a plan and make its first edit. If the agent keeps exploring, the reminder repeats every 5 calls with a stronger tone. Once any edit happens, the hook stays silent for the rest of the session.

This targets the pattern shared by all the sessions. The agent had already found the files to change in its first few calls. It then kept making one more "before editing" check: library versions, other callers, lint config, test style, changelog format, a slightly different grep. None of those checks needed to come before the first edit. The hook pushes them after the edit, where a build, test or error would surface the same facts more cheaply. The hook is not tied to any repository.

I did not run this hook or install it anywhere. Hook exit-code handling can vary between harness versions, so check that the stderr message actually reaches the agent before relying on it.

### `.factory/hooks.json`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$FACTORY_PROJECT_DIR/.factory/hooks/exploration_budget.py\"",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### `.factory/hooks/exploration_budget.py`

```python
#!/usr/bin/env python3
"""Exploration budget: nudge the agent to start editing once it has made
many read-only tool calls without a single file edit.

Reads the PostToolUse event as JSON on stdin. It exits 0 (silent) in
normal operation. When the budget is exceeded it exits 2, so the harness
shows the stderr message to the agent. Any internal error exits 0, so the
hook can never break a session.
"""
import json
import os
import re
import sys
import tempfile

FIRST_NUDGE = 10   # read-only calls before the first reminder
REPEAT_EVERY = 5   # later reminders, until an edit happens

EDIT_TOOLS = {"Edit", "MultiEdit", "Create", "Write", "ApplyPatch", "NotebookEdit"}
EXPLORE_TOOLS = {"Read", "Grep", "Glob", "LS", "Execute", "FetchUrl", "WebSearch"}

# Shell commands that clearly write source files count as an edit.
SHELL_WRITE = re.compile(r"\b(sed\s+-i|git\s+apply|patch\s+-p|tee\s+(?!/dev/null)\S)")


def state_path(session_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "default")
    return os.path.join(tempfile.gettempdir(), f"droid-explore-budget-{safe}.json")


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0

    tool = event.get("tool_name") or ""
    tool_input = event.get("tool_input") or {}
    path = state_path(event.get("session_id", ""))

    try:
        with open(path) as f:
            state = json.load(f)
    except Exception:
        state = {"edited": False, "explore": 0}

    if state.get("edited"):
        return 0

    is_edit = tool in EDIT_TOOLS or (
        tool == "Execute" and SHELL_WRITE.search(str(tool_input.get("command", "")))
    )
    if is_edit:
        state["edited"] = True
    elif tool in EXPLORE_TOOLS:
        state["explore"] = state.get("explore", 0) + 1

    try:
        with open(path, "w") as f:
            json.dump(state, f)
    except Exception:
        return 0

    n = state.get("explore", 0)
    if state["edited"] or n < FIRST_NUDGE or (n - FIRST_NUDGE) % REPEAT_EVERY:
        return 0

    strong = n >= FIRST_NUDGE + REPEAT_EVERY
    msg = (
        f"Exploration budget: {n} read/search/shell calls and no file edit yet.\n"
        + ("This is a repeat reminder. Stop exploring now.\n" if strong else "")
        + "You almost certainly know enough to start. In your next message:\n"
        "1. State the plan in 2-4 lines and name the first file you will change.\n"
        "2. Make that edit in the same turn.\n"
        "Defer remaining checks (other callers, versions, lint/test config, test "
        "style, changelog format, docs) until after the first edit. A build, test "
        "run or error message answers them faster. If a fact truly blocks the edit, "
        "fetch it with one batched call of parallel reads, then edit."
    )
    print(msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
```

**Design choices:**
- **Counting:** each call counts, including parallel ones, so a burst of 6 reads costs as much as 6 separate turns. All the sessions explored for at least 10 calls before editing.
- **Shell edits:** shell commands that clearly write source files (`sed -i`, `git apply`, `patch`, `tee`) count as edits. Ordinary `>` redirects to log files do not.
- **Message wording:** the reminder makes no reference to any specific repository. It asks for a short plan plus an edit in the same turn, so the agent can't just reply with another plan.
