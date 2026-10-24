import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).parent))
import primitives

REPO = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((REPO / "contracts" / "primitives.schema.json").read_text())
SECRET_COMMAND = "echo SECRET_TOKEN_1234 && python tests/runtests.py admin_views.tests.AdminViewTests --parallel 1"
SECRET_OUTPUT = "SECRET_OUTPUT_TEXT traceback line"


def stamp(seconds):
    return f"2026-10-24T05:00:{seconds:06.3f}Z"


def assistant(seconds, *uses):
    content = [{"type": "tool_use", "id": i, "name": n, "input": inp} for i, n, inp in uses]
    content.insert(0, {"type": "text", "text": "SECRET_ASSISTANT_TEXT"})
    return {"type": "message", "timestamp": stamp(seconds), "message": {"role": "assistant", "content": content}}


def result(seconds, *results):
    content = [{"type": "tool_result", "tool_use_id": i, "is_error": err, "content": text} for i, text, err in results]
    return {"type": "message", "timestamp": stamp(seconds), "message": {"role": "user", "content": content}}


def hook(seconds, call_id, start_s):
    message = {"role": "user", "content": [], "hookEventName": "PostToolUse", "hookToolCallId": call_id, "hookStartTime": int(start_s * 1000)}
    return {"type": "message", "timestamp": stamp(seconds), "message": message}


def epoch_of(seconds):
    return primitives.epoch(stamp(seconds))


@pytest.fixture
def session(tmp_path):
    rows = [
        {"type": "session_start", "id": "droid-1"},
        assistant(1, ("t1", "Read", {"file_path": "/testbed/pkg/mod.py"})),
        hook(1.2, "t1", epoch_of(1.1)),
        result(1.3, ("t1", "1→x = 1", False)),
        assistant(2, ("t2", "Execute", {"command": "cd /testbed && python tests/runtests.py admin_views.tests.AdminViewTests --parallel 1 2>&1 | tail -5", "summary": "targeted"})),
        hook(5.5, "t2", epoch_of(5.0)),
        result(5.6, ("t2", "Ran 3 tests\nFAILED\n\n[Process exited with code 1]", True)),
        assistant(6, ("t3", "Execute", {"command": "cd /testbed && python bin/test", "summary": "whole"}), ("t4", "Execute", {"command": "nohup python tests/runtests.py > /tmp/log 2>&1 &", "summary": "bg"})),
        hook(9, "t3", epoch_of(8.0)),
        hook(9.1, "t4", epoch_of(6.2)),
        result(9.2, ("t3", "ok\n\n[Process exited with code 0]", False), ("t4", "Status: Running in background", False)),
        assistant(10, ("t5", "Read", {"file_path": "/testbed/pkg/mod.py"}), ("t6", "Execute", {"command": SECRET_COMMAND, "summary": "again"})),
        result(11, ("t5", "1→x = 1", False), ("t6", SECRET_OUTPUT, False)),
        assistant(12, ("t7", "Execute", {"command": "cd  /testbed &&  python tests/runtests.py admin_views.tests.AdminViewTests --parallel 1 2>&1 |  tail -5", "summary": "other"})),
        result(13, ("t7", "x" * 41, False)),
        assistant(14),
    ]
    root = tmp_path / "myjob-example__example-7-2"
    transcript_dir = root / "factory-sessions" / "-testbed"
    transcript_dir.mkdir(parents=True)
    (transcript_dir / "droid-1.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    usage = {"inputTokens": 1, "outputTokens": 2, "cacheCreationTokens": 3, "cacheReadTokens": 4, "thinkingTokens": 1, "factoryCredits": 5}
    (transcript_dir / "droid-1.settings.json").write_text(json.dumps({"tokenUsage": usage}))
    (root / "meta.json").write_text(json.dumps({"droid_exit": 0}))
    return root


@pytest.fixture
def calls(session):
    return {c["tool_call_id"]: c for c in primitives.session_primitives(session)["calls"]}


def test_output_validates_against_the_schema(session):
    Draft202012Validator(SCHEMA).validate(primitives.session_primitives(session))


def test_fixture_validates_against_the_schema():
    fixture = json.loads((REPO / "contracts" / "fixtures" / "primitives.json").read_text())
    Draft202012Validator(SCHEMA).validate(fixture)


def test_session_ids_split_into_job_task_and_trial(session):
    out = primitives.session_primitives(session)
    assert (out["job_id"], out["task_id"], out["trial"]) == ("myjob", "example__example-7", 2)


def test_turns_count_assistant_messages_and_calls_know_their_turn(session):
    out = primitives.session_primitives(session)
    assert out["assistant_turns"] == 6
    assert out["tool_calls"] == 7
    assert [(c["position"], c["turn"], c["turns_after"]) for c in out["calls"]][:4] == [(0, 0, 5), (1, 1, 4), (2, 2, 3), (3, 2, 3)]


@pytest.mark.parametrize("command, expected", [
    ("python tests/runtests.py admin_views", "test"),
    ("python -m pytest -q tests/a.py", "test"),
    ("python bin/test sympy/core", "test"),
    ("python -c \"import sympy; sympy.test('sympy/core')\"", "test"),
    ("pip install -e .", "install"),
    ("sleep 30; tail -3 /tmp/log", "sleep_or_wait"),
    ("python repro.py", "run"),
    ("python - <<'EOF'\nprint(1)\nEOF", "run"),
    ("git diff | head", "vcs"),
    ("sed -i 's/a/b/' pkg/mod.py", "edit"),
    ("cat > /tmp/x.py <<'EOF'\nprint(1)\nEOF", "edit"),
    ("rg -n foo pkg | head", "search"),
    ("sed -n 1,20p pkg/mod.py", "read"),
    ("cd /testbed && echo hi", "other"),
])
def test_shell_command_classes(command, expected):
    assert primitives.classify_shell(command)[0] == expected


def test_test_command_inside_a_pipeline_stays_a_test():
    assert primitives.classify_shell("python tests/runtests.py admin 2>&1 | grep FAIL | tail -3")[0] == "test"


def test_targeted_test_run_counts_its_labels_and_skips_options(calls):
    call = calls["t2"]
    assert (call["test_runner"], call["path_arg_count"]) == ("django_runtests", 1)
    assert call["files"] == ["admin_views.tests.AdminViewTests"]


def test_whole_suite_run_has_zero_path_args(calls):
    assert (calls["t3"]["test_runner"], calls["t3"]["path_arg_count"], calls["t3"]["files"]) == ("sympy_bin_test", 0, [])


def test_non_test_calls_have_no_runner_and_no_path_arg_count(calls):
    assert (calls["t1"]["test_runner"], calls["t1"]["path_arg_count"]) == (None, None)


def test_pytest_node_ids_and_options_are_counted_correctly():
    _, test, _ = primitives.classify_shell("pytest -q -k slow -p no:cacheprovider tests/a.py::T::test_x tests/b.py")
    assert test == ("pytest", ["-q", "-k", "slow", "-p", "no:cacheprovider", "tests/a.py::T::test_x", "tests/b.py"])
    assert primitives.positionals(test[1]) == ["tests/a.py::T::test_x", "tests/b.py"]


def test_nohup_and_trailing_ampersand_mark_a_call_as_background(calls):
    assert calls["t4"]["background"] is True
    assert calls["t3"]["background"] is False


def test_duration_runs_from_tool_use_to_hook_start(calls):
    assert calls["t2"]["duration_s"] == pytest.approx(3.0, abs=0.01)
    assert calls["t4"]["duration_s"] == pytest.approx(0.2, abs=0.01)


def test_duration_falls_back_to_result_line_without_a_hook(calls):
    assert calls["t5"]["duration_s"] == pytest.approx(1.0, abs=0.01)


def test_exit_code_comes_from_the_process_trailer(calls):
    assert (calls["t2"]["exit_code"], calls["t2"]["is_error"]) == (1, True)
    assert calls["t3"]["exit_code"] == 0
    assert calls["t1"]["exit_code"] is None


def test_repeated_read_is_flagged_and_first_read_is_not(calls):
    assert calls["t1"]["repeats_earlier"] is False
    assert calls["t5"]["repeats_earlier"] is True


def test_repeated_shell_command_ignores_whitespace_and_summary(calls):
    assert calls["t2"]["repeats_earlier"] is False
    assert calls["t7"]["repeats_earlier"] is True


def test_output_size_is_chars_and_a_quarter_of_chars(calls):
    assert (calls["t7"]["output_chars"], calls["t7"]["output_tokens_est"]) == (41, 10)


def test_file_paths_are_relative_to_the_checkout(calls):
    assert calls["t1"]["files"] == ["pkg/mod.py"]


def test_call_without_a_result_has_null_result_fields(session):
    path = next(session.glob("factory-sessions/*/*.jsonl"))
    rows = path.read_text().splitlines()
    path.write_text("\n".join(r for r in rows if not ('"tool_result"' in r and '"t7"' in r)) + "\n")
    call = {c["tool_call_id"]: c for c in primitives.session_primitives(session)["calls"]}["t7"]
    assert (call["duration_s"], call["is_error"], call["output_chars"]) == (None, None, None)


def test_output_holds_no_command_or_output_text(session):
    text = json.dumps(primitives.session_primitives(session))
    for leaked in ["SECRET_TOKEN_1234", SECRET_OUTPUT, "SECRET_ASSISTANT_TEXT", "--parallel", "nohup", '"command"', '"summary"']:
        assert leaked not in text


def test_timed_out_follows_droid_exit_124(session):
    (session / "meta.json").write_text(json.dumps({"droid_exit": 124}))
    assert primitives.session_primitives(session)["timed_out"] is True
