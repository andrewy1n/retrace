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


def proxied(task, passed, **proxies):
    return result(task, 1, passed, 10, proxies=proxies)


def repo_tests(regressed, status="ok"):
    return {"status": status, "selected": ["t.py"], "regressed": regressed}


def acceptance(status, at_start="fail"):
    return {"status": status, "at_start": at_start, "check_sha256": "0" * 64}


def agreement(tmp_path, results, prim=None):
    write_job(tmp_path / "res", "a", results)
    out = tmp_path / "out.md"
    args = ["--group", "g", "--arm", "A=a", "--results", str(tmp_path / "res"), "--out", str(out)]
    if prim:
        args += ["--primitives", str(prim)]
    report.main(args)
    return out.read_text()


def test_wilson_interval_for_eight_of_ten():
    lo, hi = report.wilson(8, 10)
    assert lo == pytest.approx(0.4902, abs=1e-3)
    assert hi == pytest.approx(0.9433, abs=1e-3)


def test_kappa_known_and_undefined_cases():
    assert report.cohen_kappa(3, 1, 1, 3) == pytest.approx(0.5)
    assert math.isnan(report.cohen_kappa(4, 0, 0, 0))
    assert math.isnan(report.cohen_kappa(0, 0, 0, 0))


def test_repo_tests_counts_and_excludes_unjudged_trials(tmp_path):
    rs = [proxied("a", True, repo_tests=repo_tests(0)), proxied("b", True, repo_tests=repo_tests(0)),
          proxied("c", False, repo_tests=repo_tests(0)), proxied("d", False, repo_tests=repo_tests(2)),
          proxied("e", True, repo_tests=repo_tests(1)), proxied("f", True, repo_tests=repo_tests(0, "no_tests")),
          proxied("g", True, repo_tests=repo_tests(0, "error")), result("h", 1, True, 10)]
    text = agreement(tmp_path, rs)
    assert "| A | repo_tests | 5 | 3 | 2 | 1 | 1 | 1 | 60.0% (23.1% to 88.2%) | 0.17 | 66.7% (20.8% to 93.9%) |" in text


def test_acceptance_needs_a_failing_start_and_no_error(tmp_path):
    rs = [proxied("a", True, acceptance=acceptance("pass")), proxied("b", False, acceptance=acceptance("fail")),
          proxied("c", True, acceptance=acceptance("pass", "pass")), proxied("d", True, acceptance=acceptance("pass", "error")),
          proxied("e", True, acceptance=acceptance("error"))]
    text = agreement(tmp_path, rs)
    assert "| A | acceptance | 2 | 3 | 1 | 0 | 0 | 1 | 100.0% (34.2% to 100.0%) | 1.00 | 100.0% (20.7% to 100.0%) |" in text


def test_combined_passes_only_when_both_proxies_pass(tmp_path):
    rs = [proxied("a", True, repo_tests=repo_tests(0), acceptance=acceptance("pass")),
          proxied("b", False, repo_tests=repo_tests(0), acceptance=acceptance("fail")),
          proxied("c", True, repo_tests=repo_tests(1), acceptance=acceptance("pass")),
          proxied("d", True, repo_tests=repo_tests(0))]
    text = agreement(tmp_path, rs)
    assert "| A | combined | 3 | 1 | 1 | 0 | 1 | 1 |" in text


def test_last_test_exit_reads_the_last_test_call_with_an_exit_code(tmp_path):
    prim = tmp_path / "prim"
    prim.mkdir()

    def calls(*codes):
        return {"calls": [{"test_runner": "pytest" if code != "run" else None, "exit_code": None if code == "run" else code}
                          for code in codes]}

    (prim / "s-a-1.json").write_text(json.dumps(calls(1, 0, "run")))
    (prim / "s-b-1.json").write_text(json.dumps(calls(0, 1)))
    (prim / "s-c-1.json").write_text(json.dumps(calls("run")))
    (prim / "s-d-1.json").write_text(json.dumps(calls(0, None)))
    rs = [result(t, 1, p, 10) for t, p in [("a", True), ("b", True), ("c", True), ("d", True), ("e", True)]]
    text = agreement(tmp_path, rs, prim)
    assert "| A | last_test_exit | 2 | 3 | 1 | 0 | 1 | 0 |" in text


def test_no_proxies_says_so(tmp_path):
    text = agreement(tmp_path, [result("a", 1, True, 10)])
    assert "## Proxy agreement" in text
    assert "For verification only; the improvement loop never reads it." in text
    assert "No final trial has proxies." in text


def test_undefined_kappa_and_precision_print_na(tmp_path):
    text = agreement(tmp_path, [proxied("a", True, repo_tests=repo_tests(0)), proxied("b", True, repo_tests=repo_tests(0))])
    assert "| A | repo_tests | 2 | 0 | 2 | 0 | 0 | 0 | 100.0% (34.2% to 100.0%) | n/a | 100.0% (34.2% to 100.0%) |" in text
    text = agreement(tmp_path / "x", [proxied("a", False, repo_tests=repo_tests(3))])
    assert "| A | repo_tests | 1 | 0 | 0 | 0 | 0 | 1 | 100.0% (20.7% to 100.0%) | n/a | n/a (n/a to n/a) |" in text


def test_agreement_has_one_row_per_arm_and_an_all_row(tmp_path):
    write_job(tmp_path, "a", [proxied("x", True, repo_tests=repo_tests(0))])
    write_job(tmp_path, "c", [proxied("x", False, repo_tests=repo_tests(0))])
    out = tmp_path / "out.md"
    report.main(["--group", "g", "--arm", "A=a", "--arm", "C=c", "--results", str(tmp_path), "--out", str(out)])
    text = out.read_text()
    assert "| A | repo_tests | 1 |" in text
    assert "| C | repo_tests | 1 |" in text
    assert "| all | repo_tests | 2 |" in text


def test_diagnosis_results_without_passed_do_not_enter_agreement():
    diag = {"task_id": "x", "evidence_role": "diagnosis", "tool_call_id": "t", "proxies": {"repo_tests": repo_tests(0)}}
    n, _ = report.agreement_row("A", "repo_tests", [diag], Path("."))
    assert n == 0


def call(position, cls, runner=None, **extra):
    return {"position": position, "command_class": cls, "test_runner": runner, "path_arg_count": 0, "duration_s": 1, **extra}


def write_prim(prim, session, *calls):
    prim.mkdir(exist_ok=True)
    (prim / f"{session}.json").write_text(json.dumps({"calls": list(calls)}))


def run_report(tmp_path, arms, *extra):
    out = tmp_path / "out.md"
    args = ["--group", "g", "--results", str(tmp_path / "res"), "--out", str(out), *extra]
    for a in arms:
        args += ["--arm", a]
    report.main(args)
    return out.read_text()


def test_tests_after_last_edit_ignores_failed_edits_and_counts_later_tests():
    calls = [call(0, "edit"), call(1, "test", "pytest"), call(2, "edit"), call(3, "edit", is_error=True),
             call(4, "test", "pytest"), call(5, "test", "pytest")]
    assert report.tests_after_last_edit(calls) == 2
    assert report.skipped_verification(calls) is False
    assert report.skipped_verification(calls[:3]) is True
    assert report.tests_after_last_edit([call(0, "read")]) is None
    assert report.skipped_verification([call(0, "read")]) is None


def test_signal_difference_is_paired_by_task_with_mcnemar(tmp_path):
    prim = tmp_path / "prim"
    write_job(tmp_path / "res", "a", [result(t, 1, True, 10) for t in "xyz"])
    write_job(tmp_path / "res", "c", [result(t, 1, True, 10) for t in "xyz"])
    for t in "xyz":
        write_prim(prim, f"s-{t}-1", call(0, "test", "pytest", duration_s=90))
    text = run_report(tmp_path, ["A=a", "C=c"], "--signal", "whole_suite_tests", "--primitives", str(prim))
    assert "whole_suite_tests incidence difference (C minus A)" in text
    assert "over 3 tasks with primitives in both arms: +0.0 points" in text
    assert "Only C: 0. Exact McNemar p = 1.000" in text
    assert "Bootstrap intervals rest on 3 tasks" in text


def test_signal_difference_counts_tasks_where_only_one_arm_shows_it(tmp_path):
    prim = tmp_path / "prim"
    write_job(tmp_path / "res", "a", [result("x", 1, True, 10, session_id="sa")])
    write_job(tmp_path / "res", "c", [result("x", 1, True, 10, session_id="sc")])
    write_prim(prim, "sa", call(0, "test", "pytest", duration_s=90))
    write_prim(prim, "sc", call(0, "test", "pytest", duration_s=5))
    text = run_report(tmp_path, ["A=a", "C=c"], "--signal", "whole_suite_tests", "--primitives", str(prim))
    assert "-100.0 points" in text
    assert "Tasks where only A shows whole_suite_tests in some run: 1. Only C: 0." in text


def test_arm_row_counts_runs_without_primitives(tmp_path):
    prim = tmp_path / "prim"
    write_job(tmp_path / "res", "a", [result("x", 1, True, 10), result("y", 1, True, 10)])
    write_prim(prim, "s-x-1", call(0, "test", "pytest", duration_s=90))
    text = run_report(tmp_path, ["A=a"], "--signal", "whole_suite_tests", "--primitives", str(prim))
    assert "1 of 1 (100.0%; 20.7% to 100.0%, 1 without primitives)" in text


def test_verification_section_reports_skipped_runs_and_mean_tests(tmp_path):
    prim = tmp_path / "prim"
    write_job(tmp_path / "res", "a", [result(t, 1, True, 10) for t in "xyz"])
    write_prim(prim, "s-x-1", call(0, "edit"), call(1, "test", "pytest"), call(2, "test", "pytest"))
    write_prim(prim, "s-y-1", call(0, "edit"))
    write_prim(prim, "s-z-1", call(0, "read"))
    text = run_report(tmp_path, ["A=a"], "--primitives", str(prim))
    assert "| A | 3 | 2 | 1 of 2 (50.0%; 9.5% to 90.5%) | 1.00 |" in text


def test_credit_ratio_prints_na_when_every_trial_timed_out(tmp_path):
    write_job(tmp_path / "res", "a", [result("x", 1, True, 10, timed_out=True)])
    write_job(tmp_path / "res", "c", [result("x", 1, True, 10, timed_out=True)])
    text = run_report(tmp_path, ["A=a", "C=c"])
    assert "ratio C to A: n/a (95% interval n/a to n/a) over 0 tasks" in text


def test_trial_filter_that_leaves_an_arm_empty_is_refused(tmp_path):
    write_job(tmp_path / "res", "a", [result("x", 1, True, 10)])
    with pytest.raises(SystemExit, match="no results left"):
        run_report(tmp_path, ["A=a@2"])


def test_unknown_control_is_refused(tmp_path):
    write_job(tmp_path / "res", "a", [result("x", 1, True, 10)])
    with pytest.raises(SystemExit, match="not an arm"):
        run_report(tmp_path, ["A=a"], "--control", "Z")


def test_setup_lists_the_checkout_shas(tmp_path):
    write_job(tmp_path / "res", "a", [result("x", 1, True, 10, repo_sha="abcdef0123456789")])
    assert "(`repo_sha`): abcdef012345." in run_report(tmp_path, ["A=a"])
