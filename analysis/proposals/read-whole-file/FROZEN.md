Target `file_rereads`, frozen on 2026-10-25. Nobody edits this directory after the freeze. A revised change needs a new proposal directory and new held-out and regression tasks (the Grader section of `AGENTS.md`).

The first version (`r3-check-read-whole-file`, 2 derivation tasks) never blocked: every reread file had more than 600 lines. The revised hook (78e60b2) ran in Droid 0.249.0 on the same 2 derivation tasks (`r3-check2-read-whole-file`) unchanged. It blocked twice in each session, its message reached the model, and the agent next read a window of up to 200 lines or ran Grep with line numbers on the file. No session broke.

The runner copies only `.factory/` onto the task checkout. sha256 of each file at the freeze:

| File | sha256 |
|---|---|
| `.factory/hooks.json` | `bcfb6b32a546b0f2ecd00d457d02b4b3922efb5dd7e4cf89ad12ad94b6ba1000` |
| `.factory/hooks/read_whole_file.sh` | `cc46ea84ef5fefc8f202b3d09ec35db288c938912cde28827eac62eda33e1832` |
| `proposal.json` | `2c41744fc4f09b8b1899a3e4f2e82f089782dbe2f8b42f6ec52ddf2700001969` |
| `test_hook.sh` | `fc11d4f0f02c559110abd3c6399c431b5b8886a6babca73858ee2bc1d717bbcd` |
