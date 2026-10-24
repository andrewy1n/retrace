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
