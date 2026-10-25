import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import make_jobs

HELD = [f"instance_org{i}__repo{i}-{'a' * 8}{i}" for i in range(6)]
REGR = [f"instance_reg{i}__repo{i}-{'b' * 8}{i}" for i in range(4)]
DERIV = [f"instance_der{i}__repo{i}-{'c' * 8}{i}" for i in range(8)]


@pytest.fixture
def root(tmp_path):
    (tmp_path / "contracts").symlink_to(REPO / "contracts")
    for name, kind in (("arm-b", ".factory"), ("arm-c", "AGENTS.md")):
        d = tmp_path / "analysis" / "proposals" / name
        d.mkdir(parents=True)
        if kind == ".factory":
            (d / kind).mkdir()
            (d / kind / "hooks.json").write_text("{}")
        else:
            (d / kind).write_text("rule\n")
    return tmp_path


def write_splits(root, **over):
    splits = {"group": "g", "derivation": DERIV, "held_out": HELD, "regression": REGR, **over}
    path = root / "g.json"
    path.write_text(json.dumps(splits))
    return path


def run(root, splits, **over):
    args = {"--splits": str(splits), "--arm-b": "analysis/proposals/arm-b", "--arm-c": "analysis/proposals/arm-c",
            "--reruns": "2", "--prefix": "final1", "--budget": "2000000", "--root": str(root), **over}
    argv = [x for kv in args.items() for x in kv if x is not None]
    make_jobs.main(argv)


def jobs(root):
    return {p.stem: json.loads(p.read_text()) for p in (root / "runs" / "jobs").glob("*.json")}


def test_writes_five_valid_jobs(root, capsys):
    run(root, write_splits(root))
    j = jobs(root)
    assert sorted(j) == ["final1-heldout-a", "final1-heldout-b", "final1-heldout-c",
                         "final1-regression-a", "final1-regression-c"]
    assert j["final1-heldout-a"]["arm"] == {"kind": "control"}
    assert j["final1-heldout-b"]["arm"] == {"kind": "candidate", "path": "analysis/proposals/arm-b"}
    assert j["final1-regression-c"]["arm"] == {"kind": "candidate", "path": "analysis/proposals/arm-c"}
    assert j["final1-heldout-c"]["task_ids"] == HELD
    assert j["final1-regression-a"]["task_ids"] == REGR
    for job in j.values():
        assert job["dataset"] == "swebench_pro" and job["start"] == "step0"
        assert job["model"] == "claude-haiku-5-5" and job["stop_mode"] == "next_user_turn" and job["reruns"] == 2
    out = capsys.readouterr().out
    assert "total" in out and "estimated wall time" in out


def test_budget_splits_in_proportion_to_trials(root):
    run(root, write_splits(root), **{"--budget": "1000000"})
    j = jobs(root)
    assert j["final1-heldout-a"]["budget_credits"] == j["final1-heldout-b"]["budget_credits"] == 1000000 * 12 // 52
    assert j["final1-regression-a"]["budget_credits"] == 1000000 * 8 // 52
    assert sum(x["budget_credits"] for x in j.values()) <= 1000000


def test_warns_when_estimate_exceeds_budget(root, capsys):
    run(root, write_splits(root), **{"--budget": "500000"})
    assert "WARNING: estimate 729,300" in capsys.readouterr().err


def test_no_warning_when_budget_is_enough(root, capsys):
    run(root, write_splits(root))
    assert "WARNING" not in capsys.readouterr().err


@pytest.mark.parametrize("key,ids", [("held_out", [HELD[0], DERIV[3]]), ("regression", [REGR[0], DERIV[0]])])
def test_refuses_ids_in_derivation(root, key, ids):
    with pytest.raises(SystemExit, match=f"{key} ids also in derivation"):
        run(root, write_splits(root, **{key: ids}))
    assert not (root / "runs" / "jobs").exists()


def test_refuses_missing_proposal(root):
    with pytest.raises(SystemExit, match="arm B directory does not exist"):
        run(root, write_splits(root), **{"--arm-b": "analysis/proposals/nope"})


def test_refuses_proposal_without_overlay(root):
    (root / "analysis" / "proposals" / "empty").mkdir()
    with pytest.raises(SystemExit, match="neither .factory/ nor AGENTS.md"):
        run(root, write_splits(root), **{"--arm-c": "analysis/proposals/empty"})


def test_refuses_same_proposal_for_both_arms(root):
    with pytest.raises(SystemExit, match="same directory"):
        run(root, write_splits(root), **{"--arm-c": "analysis/proposals/arm-b"})


def test_refuses_reruns_below_two(root):
    with pytest.raises(SystemExit, match="at least 2"):
        run(root, write_splits(root), **{"--reruns": "1"})


def test_refuses_non_pro_ids(root):
    with pytest.raises(SystemExit, match="not SWE-bench Pro instance ids"):
        run(root, write_splits(root, held_out=["django__django-11099"]))


def test_refuses_existing_files_without_force(root):
    splits = write_splits(root)
    run(root, splits)
    with pytest.raises(SystemExit, match="use --force"):
        run(root, splits)
    make_jobs.main(["--splits", str(splits), "--arm-b", "analysis/proposals/arm-b", "--arm-c", "analysis/proposals/arm-c",
                    "--reruns", "3", "--prefix", "final1", "--budget", "2000000", "--root", str(root), "--force"])
    assert jobs(root)["final1-heldout-a"]["reruns"] == 3


def test_dry_run_writes_nothing(root, capsys):
    run(root, write_splits(root), **{"--dry-run": None})
    assert not (root / "runs" / "jobs").exists()
    assert "dry run" in capsys.readouterr().out


def test_invalid_job_leaves_no_files(root):
    with pytest.raises(SystemExit, match="does not validate, nothing written"):
        run(root, write_splits(root), **{"--model": ""})
    assert list((root / "runs" / "jobs").glob("*.json")) == []


STUB = """#!/usr/bin/env bash
echo "$@" >> "$STUB_LOG"
if [[ "$1" == status ]]; then
  n=$(cat "$STUB_COUNT" 2>/dev/null || echo 0); echo $((n + 1)) > "$STUB_COUNT"
  if [[ -n "${STUB_BUSY:-}" || ( $n -ge 1 && $n -lt 3 ) ]]; then echo "job-final1-heldout-a: running"; fi
fi
"""


@pytest.fixture
def repo(root, tmp_path_factory):
    r = tmp_path_factory.mktemp("repo")
    (r / "recorder" / "replay").mkdir(parents=True)
    shutil.copy(HERE / "run_final.sh", r / "recorder" / "replay" / "run_final.sh")
    shutil.copytree(root / "analysis", r / "analysis")
    (r / "contracts").mkdir()
    (r / "contracts" / "x.json").write_text("{}")
    stub = r / "stub.sh"
    stub.write_text(STUB)
    stub.chmod(0o755)
    make_jobs.main(["--splits", str(write_splits(root)), "--arm-b", "analysis/proposals/arm-b", "--arm-c",
                    "analysis/proposals/arm-c", "--reruns", "2", "--prefix", "final1", "--budget", "2000000",
                    "--root", str(root), "--out-dir", str(r / "runs" / "jobs")])
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"]):
        subprocess.run(["git", "-C", str(r), *args], check=True)
    return r


def wrapper(repo, *args, **env):
    e = {**os.environ, "RETRACE_REMOTE": str(repo / "stub.sh"), "RETRACE_POLL_S": "0",
         "STUB_LOG": str(repo / "log"), "STUB_COUNT": str(repo / "count"), "STUB_PREFIX": "final1", **env}
    return subprocess.run(["bash", str(repo / "recorder" / "replay" / "run_final.sh"), *args], env=e, capture_output=True, text=True)


def submits(repo):
    return [l.split() for l in (repo / "log").read_text().splitlines() if l.startswith("submit")]


def test_run_final_starts_regression_after_held_out(repo):
    r = wrapper(repo, "final1")
    assert r.returncode == 0, r.stderr
    s = [(Path(x[1]).stem, x[3], x[2]) for x in submits(repo)]
    assert s == [("final1-heldout-a", "3", "-d"), ("final1-heldout-b", "3", "-d"), ("final1-heldout-c", "2", "-d"),
                 ("final1-regression-a", "4", "-d"), ("final1-regression-c", "4", "-d")]
    log = (repo / "log").read_text().splitlines()
    assert max(i for i, l in enumerate(log) if l == "status") < log.index(next(l for l in log if "regression-a" in l))
    assert sum(1 for l in log if l == "status") == 4


def test_run_final_together_starts_all_five(repo):
    r = wrapper(repo, "final1", "--together")
    assert r.returncode == 0, r.stderr
    assert [x[3] for x in submits(repo)] == ["2", "2", "2", "1", "1"]


def test_run_final_refuses_when_jobs_run(repo):
    r = wrapper(repo, "final1", STUB_BUSY="1")
    assert r.returncode == 1 and "already run" in r.stderr
    assert submits(repo) == []


def test_run_final_refuses_uncommitted_overlay(repo):
    (repo / "analysis" / "proposals" / "arm-b" / "AGENTS.md").write_text("new\n")
    r = wrapper(repo, "final1")
    assert r.returncode == 1 and "Commit these first" in r.stderr
    assert not (repo / "log").exists()
