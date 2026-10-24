#!/usr/bin/env python3
"""Contract helpers for step0 jobs.

  retrace_job.py validate <job.json>
  retrace_job.py collect <job.json> <trial>
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
    if job["start"] != "step0":
        sys.exit("run_job handles step0 jobs only")
    if job["stop_mode"] != "next_user_turn":
        sys.exit("droid exec ends at the agent's final reply, so only stop_mode next_user_turn is supported")
    return job


def model_name(job):
    return f"{job['job_id']}-{job['arm']['kind']}"


def collect(job_path, trial):
    job = load_job(job_path)
    job_id, kind = job["job_id"], job["arm"]["kind"]
    eval_dir = ROOT / "runs" / job_id / f"eval-t{trial}"
    out_dir = REPO / "runs" / "results" / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ungraded = []
    for task in job["task_ids"]:
        art = ROOT / "runs" / job_id / task / str(trial)
        meta_file = art / "meta.json"
        if not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text())
        reports = sorted(eval_dir.glob(f"logs/run_evaluation/*/{model_name(job)}/{task}/report.json"))
        if reports:
            passed = bool(json.loads(reports[-1].read_text())[task]["resolved"])
        elif not (art / "patch.diff").read_text().strip():
            passed = False
        else:
            ungraded.append(task)
            continue
        result = {
            "job_id": job_id,
            "task_id": task,
            "arm": kind,
            "model": job["model"],
            "droid_version": meta["droid_version"],
            "stop_mode": job["stop_mode"],
            "trial": trial,
            "passed": passed,
            "grader": "swebench",
            "evidence_role": "final",
            "cost_credits": meta["cost_credits"],
        }
        session_id = f"{job_id}-{task}-{trial}"
        if (REPO / "runs" / "traces" / f"{session_id}.json").exists():
            result["session_id"] = session_id
        check(result, "replay-result")
        (out_dir / f"{task}-step0-{kind}-{trial}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(f"{task} trial {trial}: {'pass' if passed else 'fail'}")
    if ungraded:
        sys.exit(f"no grader report for: {', '.join(ungraded)}")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "validate":
        load_job(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "collect":
        collect(sys.argv[2], int(sys.argv[3]))
    else:
        sys.exit(__doc__)


main()
