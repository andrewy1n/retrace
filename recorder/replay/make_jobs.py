#!/usr/bin/env python3
"""Write the step-0 held-out and regression jobs for one split.

  make_jobs.py --splits splits/<group>.json [--arm-b <path>] --arm-c <path> --reruns N --prefix P --budget CREDITS

Writes runs/jobs/<P>-heldout-{a,c}.json and <P>-regression-{a,c}.json. Arm A is control. With --arm-b it also writes
<P>-heldout-b.json.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PRO_MEAN_CREDITS = 14025
PRO_MAX_CREDITS = 70057
DROID_MEAN_S = 260
DROID_MEDIAN_S = 213
GRADE_H_PER_132 = 0.6
ALPINE_SUFFIX = "-vee9b09fb20c43af7e520f57e9239bbcf46b7113d"
VALIDATOR = Path(__file__).resolve().parents[1] / "worker" / "scripts" / "retrace_job.py"

JOBS = [("heldout", "held_out", "a"), ("heldout", "held_out", "b"), ("heldout", "held_out", "c"),
        ("regression", "regression", "a"), ("regression", "regression", "c")]


def fail(msg):
    sys.exit(f"error: {msg}")


def read_ids(splits, key):
    ids = splits.get(key)
    if not isinstance(ids, list) or not all(isinstance(i, str) and i for i in ids):
        fail(f"splits.{key} must be a list of instance ids")
    if len(set(ids)) != len(ids):
        fail(f"splits.{key} has duplicate ids")
    return ids


def load_splits(path):
    splits = json.loads(Path(path).read_text())
    if not isinstance(splits.get("group"), str) or not splits["group"]:
        fail("splits.group is missing")
    lists = {k: read_ids(splits, k) for k in ("derivation", "held_out", "regression")}
    for key in ("held_out", "regression"):
        if not lists[key]:
            fail(f"splits.{key} is empty")
        leaked = sorted(set(lists[key]) & set(lists["derivation"]))
        if leaked:
            fail(f"{key} ids also in derivation: {', '.join(leaked)}")
    for key, ids in lists.items():
        bad = [i for i in ids if not i.startswith("instance_")]
        if bad:
            fail(f"splits.{key} has ids that are not SWE-bench Pro instance ids: {', '.join(bad)}")
    return splits["group"], lists


def check_proposal(root, label, rel):
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        fail(f"{label} path must be relative to the repo and portable: {rel}")
    d = root / p
    if not d.is_dir():
        fail(f"{label} directory does not exist: {d}")
    if not ((d / ".factory").is_dir() or (d / "AGENTS.md").is_file()):
        fail(f"{label} directory holds neither .factory/ nor AGENTS.md: {d}")
    return p.as_posix()


def build_job(job_id, tasks, arm, model, reruns, budget):
    return {"job_id": job_id, "dataset": "swebench_pro", "start": "step0", "task_ids": tasks, "arm": arm,
            "model": model, "reruns": reruns, "stop_mode": "next_user_turn", "budget_credits": budget}


def validate(root, path):
    env = {**os.environ, "RETRACE_REPO": str(root), "RETRACE_ROOT": str(root)}
    r = subprocess.run([sys.executable, str(VALIDATOR), "validate", str(path)], env=env, capture_output=True, text=True)
    if r.returncode:
        return (r.stderr or r.stdout).strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--splits", required=True)
    ap.add_argument("--arm-b", help="transcript-only overlay directory, relative to the repo (optional)")
    ap.add_argument("--arm-c", required=True, help="replay-derived overlay directory, relative to the repo")
    ap.add_argument("--reruns", required=True, type=int, help="reruns per task per arm (pre-registration: at least 2)")
    ap.add_argument("--prefix", required=True, help="job-id prefix, such as final1")
    ap.add_argument("--budget", required=True, type=float, help="total Factory credits for all jobs")
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--parallel", type=int, default=8, help="trials in flight at once")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]), help="repo root")
    ap.add_argument("--out-dir", help="default <root>/runs/jobs")
    ap.add_argument("--force", action="store_true", help="overwrite existing job files")
    ap.add_argument("--dry-run", action="store_true", help="check and print the plan, write nothing")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    out = Path(args.out_dir) if args.out_dir else root / "runs" / "jobs"
    if args.reruns < 2:
        fail("reruns must be at least 2 (pre-registration)")
    if args.budget <= 0:
        fail("budget must be positive")

    group, ids = load_splits(args.splits)
    arm_b = check_proposal(root, "arm B", args.arm_b) if args.arm_b else None
    arm_c = check_proposal(root, "arm C", args.arm_c)
    if arm_b == arm_c:
        fail("arm B and arm C are the same directory")

    arms = {"a": {"kind": "control"}, "c": {"kind": "candidate", "path": arm_c}}
    if arm_b:
        arms["b"] = {"kind": "candidate", "path": arm_b}
    plan = [(f"{args.prefix}-{kind}-{arm}", ids[key], arms[arm]) for kind, key, arm in JOBS if arm in arms]
    n_trials = {jid: len(tasks) * args.reruns for jid, tasks, _ in plan}
    total = sum(n_trials.values())
    budgets = {jid: int(args.budget * n / total) for jid, n in n_trials.items()}

    existing = [out / f"{jid}.json" for jid, _, _ in plan if (out / f"{jid}.json").exists()]
    if existing and not args.force and not args.dry_run:
        fail("job files exist (use --force): " + ", ".join(str(p) for p in existing))

    jobs = [build_job(jid, tasks, arm, args.model, args.reruns, budgets[jid]) for jid, tasks, arm in plan]
    if not args.dry_run:
        out.mkdir(parents=True, exist_ok=True)
        written = []
        for job in jobs:
            path = out / f"{job['job_id']}.json"
            path.write_text(json.dumps(job, indent=2) + "\n")
            written.append(path)
        for path in written:
            problem = validate(root, path)
            if problem:
                for p in written:
                    p.unlink()
                fail(f"{path.name} does not validate, nothing written: {problem}")

    print(f"group {group}: derivation {len(ids['derivation'])}, held_out {len(ids['held_out'])}, regression {len(ids['regression'])}")
    print(f"model {args.model}, reruns {args.reruns}, dataset swebench_pro, stop_mode next_user_turn")
    if arm_b:
        print(f"arm B {arm_b}")
    print(f"arm C {arm_c}")
    print(f"\n{'job':<34}{'tasks':>6}{'trials':>8}{'budget':>12}{'est. credits':>14}")
    for job in jobs:
        n = n_trials[job["job_id"]]
        print(f"{job['job_id']:<34}{len(job['task_ids']):>6}{n:>8}{job['budget_credits']:>12,}{n * PRO_MEAN_CREDITS:>14,}")
    est = total * PRO_MEAN_CREDITS
    print(f"{'total':<34}{'':>6}{total:>8}{sum(budgets.values()):>12,}{est:>14,}")

    grade_h = total / 132 * GRADE_H_PER_132
    mean_h = total * DROID_MEAN_S / args.parallel / 3600 + grade_h
    median_h = total * DROID_MEDIAN_S / args.parallel / 3600 + grade_h
    print(f"\nestimated wall time at {args.parallel} parallel: {mean_h:.1f} h (mean {DROID_MEAN_S} s per trial), "
          f"{median_h:.1f} h (median {DROID_MEDIAN_S} s), each including {grade_h:.1f} h of grading")
    print(f"worst-case overshoot past the budget: {args.parallel * PRO_MAX_CREDITS:,} credits "
          f"({args.parallel} trials in flight x {PRO_MAX_CREDITS:,} maximum)")
    if est > args.budget:
        print(f"WARNING: estimate {est:,} credits exceeds the budget {int(args.budget):,}. run_job.sh stops starting trials "
              "at the cap, so the last trials of each job do not run.", file=sys.stderr)
    elif est + args.parallel * PRO_MAX_CREDITS > args.budget:
        print(f"note: estimate plus worst-case overshoot exceeds the budget {int(args.budget):,}.")
    overlap = sorted(set(ids["held_out"]) & set(ids["regression"]))
    if overlap:
        print(f"WARNING: {len(overlap)} id(s) are in both held_out and regression: {', '.join(overlap)}", file=sys.stderr)
    alpine = sorted(i for k in ("held_out", "regression") for i in ids[k] if i.endswith(ALPINE_SUFFIX))
    if alpine:
        print(f"WARNING: Alpine image(s), the Droid binary cannot run there: {', '.join(alpine)}", file=sys.stderr)
    print("\ndry run, nothing written" if args.dry_run else f"\nwrote {len(jobs)} job files to {out}, all valid")


if __name__ == "__main__":
    main()
