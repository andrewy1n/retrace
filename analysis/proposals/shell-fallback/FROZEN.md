Workaround for the Droid 0.249.0 defect that reports every foreground `Execute` call as killed (SIGKILL) in an image without `ps` (procps). Target `shell_error_streak`, frozen on 2026-10-25. Nobody edits this directory after the freeze. A revised change needs a new proposal directory and new held-out and regression tasks (the Grader section of `AGENTS.md`).

It ran in Droid 0.249.0 on four derivation tasks (`r2-check-shell-fallback`). It fired once per session in all four, its message reached the model, and the agent moved to `fireAndForget` runs. No session broke. Twice Droid refused the first background command because it wrote to `/dev/null`, so the message now says to avoid that. The frozen message has run only in `test_hook.sh`.

The runner copies only `.factory/` onto the task checkout. sha256 of each file at the freeze:

| File | sha256 |
|---|---|
| `.factory/hooks.json` | `95b07e6b53edb0370f56bc2a0b9b53c79bba6ffda5279de0c1b3a005b11f8681` |
| `.factory/hooks/shell_fallback.sh` | `e00e17ef270889091a57b0bc8c1e60aa839fb4e62d1c919784de316e5c6824e8` |
| `proposal.json` | `4d90efe6ae09c614e4cd77518b237c854c8678ad67a203f43cf5f728f0e27168` |
| `test_hook.sh` | `1895e4aa792bfefccbccca0c040b17520392b984e7ad2c2310253f69507c7608` |
