Target `large_root_searches`, frozen on 2026-10-25. Nobody edits this directory after the freeze. A revised change needs a new proposal directory and new held-out and regression tasks (the Grader section of `AGENTS.md`).

It ran in Droid 0.249.0 on four derivation tasks (`r2-check-root-search-limit`) unchanged. It fired in three of them, once each, its message reached the model, and the agent searched with `file_paths` or a narrower path next. The fourth session made no content search over the repo root. No session broke.

The runner copies only `.factory/` onto the task checkout. sha256 of each file at the freeze:

| File | sha256 |
|---|---|
| `.factory/hooks.json` | `09f61c6f39f846c7208ed2e5a7bf46b124c8242504ac7aa320c1e0db0dba6ad4` |
| `.factory/hooks/root_search_limit.sh` | `cadb5c34bb117a56e30c03f326bedd4005e50468aa75f9ce5c4acda6d7a99684` |
| `proposal.json` | `d0c6da74e9f75be691c733a0137893629277725eba4f665fe7f2f1d9024603ea` |
| `test_hook.sh` | `d3c816a76974dcc217776dd1e48ea0bdefd734ea38b8f702979c7fbcdb9c6a56` |
