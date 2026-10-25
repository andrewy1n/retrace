import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import ship_pr

TASKS = ["instance_org__repo-1", "instance_org__repo-2"]


def job(job_id, arm):
    return {"job_id": job_id, "dataset": "swebench_pro", "start": "step0", "task_ids": TASKS, "arm": arm,
            "model": "m", "reruns": 2, "stop_mode": "next_user_turn", "budget_credits": 1}


def write_results(root, job_id, passes, credits, first_edit):
    out = root / "runs" / "results" / job_id
    out.mkdir(parents=True)
    for i, task in enumerate(TASKS):
        for trial in (1, 2):
            sid = f"{job_id}-{i}-{trial}"
            (out / f"{task}-step0-x-{trial}.json").write_text(json.dumps({
                "job_id": job_id, "task_id": task, "session_id": sid, "trial": trial, "model": "m", "droid_version": "1",
                "evidence_role": "final", "grader": "swebench_pro", "passed": passes[i], "cost_credits": credits,
                "proxies": {"repo_tests": {"status": "ok"}}}))
            calls = [{"position": p, "command_class": "edit" if p == first_edit else "read"} for p in range(1, 21)]
            (root / "runs" / "primitives" / f"{sid}.json").write_text(json.dumps({"calls": calls}))


@pytest.fixture
def root(tmp_path):
    (tmp_path / "runs" / "jobs").mkdir(parents=True)
    (tmp_path / "runs" / "primitives").mkdir(parents=True)
    d = tmp_path / "analysis" / "proposals" / "p" / ".factory" / "hooks"
    d.mkdir(parents=True)
    (d / "hook.sh").write_text("#!/bin/sh\n# Block one call after ten with no edit.\n# It fires once.\n\nexit 0\n")
    (d.parent / "hooks.json").write_text("{}")
    prop = {"proposal_id": "p", "cost_pattern": "calls_before_first_edit", "change_type": "guardrail_hook",
            "path": "analysis/proposals/p"}
    (tmp_path / "analysis" / "proposals" / "p" / "proposal.json").write_text(json.dumps(prop))
    for j in (job("x-heldout-a", {"kind": "control"}),
              job("x-heldout-c", {"kind": "candidate", "path": "analysis/proposals/p"}),
              job("y-check-c", {"kind": "candidate", "path": "analysis/proposals/p"})):
        (tmp_path / "runs" / "jobs" / f"{j['job_id']}.json").write_text(json.dumps(j))
    write_results(tmp_path, "x-heldout-a", [True, True], 1000, 15)
    write_results(tmp_path, "x-heldout-c", [True, False], 800, 3)
    return tmp_path


def body(root):
    proposal_dir = root / "analysis" / "proposals" / "p"
    proposal = json.loads((proposal_dir / "proposal.json").read_text())
    pairs = ship_pr.find_pairs(root, proposal["path"], "x-")
    return ship_pr.build_body(proposal_dir, proposal, pairs, root / "runs" / "results", root / "runs" / "primitives")


def test_pairs_candidate_with_control_on_the_same_tasks(root):
    pairs = ship_pr.find_pairs(root, "analysis/proposals/p", "x-")
    assert [(c["job_id"], k["job_id"]) for c, k in pairs] == [("x-heldout-a", "x-heldout-c")]


def test_refuses_when_no_job_pairs(root):
    with pytest.raises(SystemExit, match="no candidate job"):
        ship_pr.find_pairs(root, "analysis/proposals/p", "y-")


def test_body_reports_counts_harm_and_rollback(root):
    text = body(root)
    assert "| Passed | 4 of 4 | 2 of 4 |" in text
    assert "| Runs with more than 12 calls before the first edit | 4 of 4 | 0 of 4 |" in text
    assert "tasks that pass every baseline rerun and fail a rerun with the change: 1" in text
    assert "Block one call after ten with no edit. It fires once." in text
    assert "Remove `.factory/hooks/hook.sh`, `.factory/hooks.json`" in text
    assert text.rstrip().endswith("`runs/primitives/`.")


def test_body_avoids_internal_vocabulary(root):
    text = body(root).lower()
    for word in ("arm a", "arm c", "gate", "amendment", "pre-registration"):
        assert word not in text


def test_frozen_hash_follows_proposal_json(root):
    d = root / "analysis" / "proposals" / "p"
    (d / "FROZEN.md").write_text("| `proposal.json` | `" + "0" * 64 + "` |\n")
    ship_pr.set_pr_url(d, json.loads((d / "proposal.json").read_text()), "https://example.com/pull/2")
    import hashlib
    digest = hashlib.sha256((d / "proposal.json").read_bytes()).hexdigest()
    assert (d / "FROZEN.md").read_text() == f"| `proposal.json` (with `pr_url`) | `{digest}` |\n"
