#!/usr/bin/env python3
"""Contract helpers for step0 and checkpoint jobs.

  retrace_job.py validate <job.json>
  retrace_job.py collect <job.json> <trial> [tool_call_id]
"""
import json
import os
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(os.environ.get("RETRACE_ROOT", "/opt/retrace"))
REPO = Path(os.environ.get("RETRACE_REPO", ROOT / "repo"))


def schema(name):
    return json.loads((REPO / "contracts" / f"{name}.schema.json").read_text())


def check(instance, name):
    errors = sorted(Draft202012Validator(schema(name)).iter_errors(instance), key=str)
    if errors:
        sys.exit(f"{name}: " + "; ".join(e.message for e in errors))


def load_job(path):
    job = json.loads(Path(path).read_text())
    check(job, "replay-job")
    if job["stop_mode"] != "next_user_turn":
        sys.exit("a trial ends at the agent's final reply, so only stop_mode next_user_turn is supported")
    if job["start"] == "checkpoint":
        trace = load_trace(job["session_id"])
        missing = set(job["tool_call_ids"]) - {s["tool_call_id"] for s in trace["steps"]}
        if missing:
            sys.exit(f"tool_call_ids not in trace {job['session_id']}: {', '.join(sorted(missing))}")
    return job


def load_trace(session_id):
    path = REPO / "runs" / "traces" / f"{session_id}.json"
    if not path.exists():
        sys.exit(f"no trace at {path}")
    return json.loads(path.read_text())


def model_name(job):
    return f"{job['job_id']}-{job['arm']['kind']}"


def trials(job, trial, only):
    runs = ROOT / "runs" / job["job_id"]
    if job["start"] == "step0":
        for task in job["task_ids"]:
            yield task, "step0", runs / task / str(trial), runs / f"eval-t{trial}"
        return
    task = load_trace(job["session_id"])["task_id"]
    for cp in [only] if only else job["tool_call_ids"]:
        yield task, cp, runs / task / cp / str(trial), None


def graded(job, eval_dir, task):
    if job.get("dataset") == "swebench_pro":
        reward = eval_dir / task / "reward.txt"
        return reward.read_text().strip() == "1" if reward.exists() else None
    reports = sorted(eval_dir.glob(f"logs/run_evaluation/*/{model_name(job)}/{task}/report.json"))
    return bool(json.loads(reports[-1].read_text())[task]["resolved"]) if reports else None


def collect(job_path, trial, only=None):
    job = load_job(job_path)
    job_id, kind = job["job_id"], job["arm"]["kind"]
    out_dir = REPO / "runs" / "results" / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    problems = []
    for task, cp, art, eval_dir in trials(job, trial, only):
        meta_file = art / "meta.json"
        if not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text())
        if meta.get("failed"):
            problems.append(f"{task} {cp}: trial failed: {meta['failed']}")
            continue
        if cp == "step0":
            passed = graded(job, eval_dir, task)
            if passed is None and not (art / "patch.diff").read_text().strip():
                passed = False
            elif passed is None:
                problems.append(f"{task} {cp}: no grader report")
                continue
        result = {
            "job_id": job_id,
            "task_id": task,
            "arm": kind,
            "model": meta.get("model", job["model"]),
            "droid_version": meta["droid_version"],
            "stop_mode": job["stop_mode"],
            "trial": trial,
            "evidence_role": "final" if cp == "step0" else "diagnosis",
            "cost_credits": meta["cost_credits"],
        }
        if cp == "step0":
            result["passed"] = passed
            result["grader"] = "swebench_pro" if job.get("dataset") == "swebench_pro" else "swebench"
        else:
            result["tool_call_id"] = cp
        proxies_file = art / "proxies.json"
        if proxies_file.exists():
            result["proxies"] = json.loads(proxies_file.read_text())
        else:
            print(f"warning: {task} {cp} trial {trial}: no proxies.json, result has no proxies", file=sys.stderr)
        if "timed_out" in meta:
            result["timed_out"] = meta["timed_out"]
        session_id = f"{job_id}-{task}-{trial}"
        if cp == "step0" and (REPO / "runs" / "traces" / f"{session_id}.json").exists():
            result["session_id"] = session_id
        check(result, "replay-result")
        (out_dir / f"{task}-{cp}-{kind}-{trial}.json").write_text(json.dumps(result, indent=2) + "\n")
        outcome = "collected" if cp != "step0" else "pass" if passed else "fail"
        print(f"{task} {cp} trial {trial}: {outcome}")
    if problems:
        sys.exit("; ".join(problems))


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "validate":
        load_job(sys.argv[2])
    elif len(sys.argv) in (4, 5) and sys.argv[1] == "collect":
        collect(sys.argv[2], int(sys.argv[3]), sys.argv[4] if len(sys.argv) == 5 else None)
    else:
        sys.exit(__doc__)


main()
