Commit one file per target (a failure group or a cost pattern), `splits/<group>.json`, before anyone studies the held-out tasks. About two thirds of the sessions are derivation and about one third are held out. Regression tasks come from the dev repos and stay out of derivation, like held-out tasks (the Grader section of `AGENTS.md`). `recorder/replay/make_jobs.py` refuses a split where they overlap.

```json
{
  "group": "large_reads",
  "derivation": ["instance-id"],
  "held_out": ["instance-id"],
  "regression": ["instance-id"]
}
```

Ids are SWE-bench instance ids. Held-out tasks come from different repos than the derivation tasks.

`splits/pool.json` lists the dev and held-out tasks. `splits/draw_pool.py` draws it from fixed quotas and a seed. The current pool keeps the baseline1 dev tasks and was drawn before any run on its new tasks. Nobody runs or studies the held-out tasks until the change is frozen (Gate 4). The per-group files above pick from this pool.

On SWE-bench Pro, `python splits/pro_split.py --group <target>` writes `splits/<target>.json` from `splits/pro-pool.json`. A seeded shuffle within each dev repo (seed 19) holds back 2 tasks per repo as regression, 8 in all, and the other 21 dev tasks are derivation. Held-out is the pool's 22 held-out tasks. The draw reads no outcome and does not depend on `--group`. `splits/draft.json` holds the same ids under the group `draft` until the target is chosen.
