Commit one file per failure group, `splits/<group>.json`, before anyone studies the held-out tasks. The hackathon pool is 20 to 40 tasks. About two thirds of the sessions are derivation and about one third are held out. The regression list is about ten good past sessions, including legitimate test edits.

```json
{
  "group": "test_gaming",
  "derivation": ["instance-id"],
  "held_out": ["instance-id"],
  "regression": ["instance-id"]
}
```

Ids are SWE-bench instance ids. Held-out tasks come from different repos than the derivation tasks.

`splits/pool.json` lists the dev and held-out tasks. `splits/draw_pool.py` draws it from fixed quotas and a seed. The current pool keeps the baseline1 dev tasks and was drawn before any run on its new tasks. Nobody runs or studies the held-out tasks until the change is frozen (Gate 4). The per-group files above pick from this pool.
