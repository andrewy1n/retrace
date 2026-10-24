import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import report


def result(task, trial, passed, credits, **extra):
    return {"task_id": task, "trial": trial, "passed": passed, "cost_credits": credits, "evidence_role": "final",
            "model": "m", "droid_version": "1", "grader": "swebench_pro", "session_id": f"s-{task}-{trial}", **extra}


def write_job(root, job, results):
    d = root / job
    d.mkdir(parents=True)
    for i, r in enumerate(results):
        (d / f"{i}.json").write_text(json.dumps(r))


def test_wilson_matches_known_interval():
    lo, hi = report.wilson(0, 29)
    assert lo == 0.0
    assert hi == pytest.approx(0.1170, abs=1e-3)


def test_mcnemar_exact_two_sided():
    assert report.mcnemar_exact(5, 0) == pytest.approx(0.0625)
    assert report.mcnemar_exact(0, 0) == 1.0


def test_paired_report_counts_and_ratio(tmp_path):
    write_job(tmp_path, "a", [result(t, 1, True, 1000) for t in "xyz"] + [result("w", 1, False, 1000)])
    write_job(tmp_path, "c", [result(t, 1, True, 500) for t in "xyz"] + [result("w", 1, True, 500)])
    out = tmp_path / "out.md"
    report.main(["--group", "g", "--arm", "A=a", "--arm", "C=c", "--results", str(tmp_path), "--out", str(out)])
    text = out.read_text()
    assert "| A | 4 | 4 | 3 | 75.0%" in text
    assert "Only C: 1" in text
    assert "ratio C to A: 0.500" in text


def test_timed_out_trials_are_left_out_of_credits(tmp_path):
    write_job(tmp_path, "a", [result("x", 1, True, 1000), result("x", 2, True, 0, timed_out=True)])
    out = tmp_path / "out.md"
    report.main(["--group", "g", "--arm", "A=a", "--results", str(tmp_path), "--out", str(out)])
    assert "| A | 1 | 2 | 2 | 100.0% (34.2% to 100.0%) | 1 | 1,000 | 1,000 |" in out.read_text()


def test_diagnosis_results_are_refused(tmp_path):
    write_job(tmp_path, "a", [result("x", 1, True, 1, evidence_role="diagnosis")])
    with pytest.raises(SystemExit, match="not final evidence"):
        report.main(["--group", "g", "--arm", "A=a", "--results", str(tmp_path)])


def test_arms_with_different_models_are_refused(tmp_path):
    write_job(tmp_path, "a", [result("x", 1, True, 1)])
    write_job(tmp_path, "c", [result("x", 1, True, 1, model="other")])
    with pytest.raises(SystemExit, match="differ in model"):
        report.main(["--group", "g", "--arm", "A=a", "--arm", "C=c", "--results", str(tmp_path)])


def test_signal_counts_runs_with_a_whole_suite_call(tmp_path):
    write_job(tmp_path / "res", "a", [result("x", 1, True, 10), result("y", 1, True, 10)])
    prim = tmp_path / "prim"
    prim.mkdir()
    call = {"test_runner": "pytest", "path_arg_count": 0, "duration_s": 90}
    (prim / "s-x-1.json").write_text(json.dumps({"calls": [call]}))
    (prim / "s-y-1.json").write_text(json.dumps({"calls": [{**call, "path_arg_count": 2}]}))
    out = tmp_path / "out.md"
    report.main(["--group", "g", "--arm", "A=a", "--signal", "whole_suite_tests", "--results", str(tmp_path / "res"),
                 "--primitives", str(prim), "--out", str(out)])
    assert "1 of 2 (50.0%" in out.read_text()
