import hashlib
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).parent))
import repo_tests

REPO = Path(__file__).resolve().parents[3]
RESULT_SCHEMA = json.loads((REPO / "contracts" / "replay-result.schema.json").read_text())
PROXIES = Draft202012Validator({**RESULT_SCHEMA["properties"]["proxies"], "$schema": RESULT_SCHEMA["$schema"]})

PATCH = '''diff --git a/pkg/foo.py b/pkg/foo.py
index 111..222 100644
--- a/pkg/foo.py
+++ b/pkg/foo.py
@@ -1,2 +1,2 @@
-old
--- a/not/a/header.py
+new
diff --git a/pkg/new_mod.py b/pkg/new_mod.py
new file mode 100644
--- /dev/null
+++ b/pkg/new_mod.py
@@ -0,0 +1 @@
+x
diff --git a/pkg/gone.py b/pkg/gone.py
deleted file mode 100644
--- a/pkg/gone.py
+++ /dev/null
@@ -1 +0,0 @@
-x
diff --git a/tests/test_foo.py b/tests/test_foo.py
--- a/tests/test_foo.py
+++ b/tests/test_foo.py
@@ -1 +1 @@
-a
+b
diff --git a/old_name.py b/new_name.py
similarity index 90%
rename from old_name.py
rename to new_name.py
'''

JUNIT = """<?xml version="1.0"?>
<testsuites><testsuite name="pytest" tests="5">
<testcase classname="tests.test_a" name="test_pass" time="0.1"/>
<testcase classname="tests.test_a" name="test_fail"><failure message="boom">trace</failure></testcase>
<testcase classname="tests.test_a" name="test_error"><error message="setup">trace</error></testcase>
<testcase classname="tests.test_a" name="test_skip"><skipped message="why"/></testcase>
<testcase classname="tests.test_b" name="test_other"/>
</testsuite></testsuites>"""

GO_STREAM = "\n".join(
    json.dumps(e)
    for e in [
        {"Action": "start", "Package": "m/pkg"},
        {"Action": "run", "Package": "m/pkg", "Test": "TestA"},
        {"Action": "output", "Package": "m/pkg", "Test": "TestA", "Output": "ok\n"},
        {"Action": "pass", "Package": "m/pkg", "Test": "TestA"},
        {"Action": "run", "Package": "m/pkg", "Test": "TestB"},
        {"Action": "fail", "Package": "m/pkg", "Test": "TestB"},
        {"Action": "run", "Package": "m/pkg", "Test": "TestC"},
        {"Action": "skip", "Package": "m/pkg", "Test": "TestC"},
        {"Action": "run", "Package": "m/pkg", "Test": "TestHung"},
        {"Action": "fail", "Package": "m/pkg"},
    ]
)


def test_edited_paths_cover_new_deleted_renamed_and_ignore_hunk_lines():
    assert repo_tests.edited_paths(PATCH) == [
        "pkg/foo.py", "pkg/new_mod.py", "pkg/gone.py", "tests/test_foo.py", "old_name.py", "new_name.py",
    ]


def test_edited_paths_unquote_special_names():
    patch = 'diff --git "a/d/f\\303\\251.py" "b/d/f\\303\\251.py"\n--- "a/d/f\\303\\251.py"\n+++ "b/d/f\\303\\251.py"\n@@ -1 +1 @@\n-a\n+b\n'
    assert repo_tests.edited_paths(patch) == ["d/fé.py"]


def test_edited_paths_empty_patch():
    assert repo_tests.edited_paths("") == []


@pytest.mark.parametrize("path", [
    "test_foo.py", "pkg/foo_test.py", "tests/helpers.py", "a/testing/util.py", "a/conftest.py",
    "tests/data/x.json", "pkg/foo_test.go",
])
def test_test_files_are_recognised(path):
    assert repo_tests.is_test_file(path)


@pytest.mark.parametrize("path", ["pkg/foo.py", "pkg/contest.py", "pkg/foo.go", "pkg/latest_foo.py", "pkg/testing_util/x.py"])
def test_source_files_are_not_test_files(path):
    assert not repo_tests.is_test_file(path)


def test_python_selection_matches_both_naming_styles_and_ignores_missing_files():
    tree = ["pkg/foo.py", "tests/test_foo.py", "tests/bar_test.py", "tests/test_other.py"]
    sel = repo_tests.select(["pkg/foo.py", "pkg/bar.py", "pkg/baz.py"], tree)
    assert sel["selected"] == ["tests/test_foo.py", "tests/bar_test.py"]
    assert sel["python"] == sel["selected"]
    assert sel["go_dirs"] == []


def test_python_selection_prefers_the_longest_shared_directory_prefix():
    tree = [
        "a/b/c/x.py", "a/b/c/tests/test_x.py", "a/b/tests/test_x.py", "a/tests/test_x.py", "z/test_x.py", "x_test.py",
    ]
    sel = repo_tests.select(["a/b/c/x.py"], tree)
    assert sel["selected"] == [
        "a/b/c/tests/test_x.py", "a/b/tests/test_x.py", "a/tests/test_x.py", "x_test.py", "z/test_x.py",
    ]


def test_python_selection_is_capped_at_ten_and_spreads_over_sources():
    tree = [f"t{i}/test_big.py" for i in range(12)] + ["t/test_small.py"]
    sel = repo_tests.select(["src/big.py", "src/small.py"], tree)
    assert len(sel["selected"]) == 10
    assert "t/test_small.py" in sel["selected"]


def test_python_selection_ignores_edited_test_files_and_other_languages():
    tree = ["tests/test_foo.py", "pkg/foo.py", "tests/test_test_foo.py"]
    sel = repo_tests.select(["tests/test_foo.py", "README.md", "setup.cfg"], tree)
    assert sel["selected"] == []


def test_go_selection_takes_package_dirs_that_have_tests_at_start():
    tree = [
        "go.mod", "main.go", "main_test.go", "internal/a/a.go", "internal/a/a_test.go", "internal/a/b_test.go",
        "internal/b/b.go", "internal/c/c_test.go",
    ]
    sel = repo_tests.select(["internal/a/a.go", "internal/a/other.go", "internal/b/b.go", "main.go", "internal/a/a_test.go"], tree)
    assert sel["selected"] == ["internal/a", "."]
    assert sel["go_dirs"] == ["internal/a", "."]
    assert sel["go_runs"] == [{"module": ".", "pkgs": ["./internal/a", "."]}]
    assert sel["restore"] == ["internal/a/a_test.go", "internal/a/b_test.go", "main_test.go"]


def test_go_selection_is_capped_at_five_dirs():
    tree = [f"p{i}/x.go" for i in range(8)] + [f"p{i}/x_test.go" for i in range(8)]
    sel = repo_tests.select([f"p{i}/x.go" for i in range(8)], tree)
    assert sel["go_dirs"] == [f"p{i}" for i in range(5)]


def test_go_selection_runs_each_package_in_its_nearest_module():
    tree = ["go.mod", "api/go.mod", "api/types/t.go", "api/types/t_test.go", "lib/l.go", "lib/l_test.go"]
    sel = repo_tests.select(["api/types/t.go", "lib/l.go"], tree)
    assert sel["go_runs"] == [
        {"module": "api", "pkgs": ["./types"]},
        {"module": ".", "pkgs": ["./lib"]},
    ]


def test_go_selection_skips_dirs_without_tests():
    sel = repo_tests.select(["cmd/main.go"], ["cmd/main.go", "other/x_test.go"])
    assert sel["selected"] == []


def test_selection_key_ignores_order_and_changes_with_content():
    a = repo_tests.select(["a.py", "b.py"], ["test_a.py", "test_b.py"])
    b = repo_tests.select(["b.py", "a.py"], ["test_a.py", "test_b.py"])
    c = repo_tests.select(["a.py"], ["test_a.py", "test_b.py"])
    assert a["key"] == b["key"] != c["key"]


def test_junit_outcomes():
    assert repo_tests.parse_junit(JUNIT) == {
        "tests.test_a::test_pass": "pass",
        "tests.test_a::test_fail": "fail",
        "tests.test_a::test_error": "error",
        "tests.test_a::test_skip": "skip",
        "tests.test_b::test_other": "pass",
    }


def test_junit_duplicate_ids_keep_the_worst_outcome():
    xml = '<testsuite><testcase classname="c" name="t"/><testcase classname="c" name="t"><error/></testcase></testsuite>'
    assert repo_tests.parse_junit(xml) == {"c::t": "error"}


def test_junit_that_does_not_parse_is_an_error():
    with pytest.raises(ValueError, match="does not parse"):
        repo_tests.parse_junit("")


def test_go_test2json_outcomes_and_interrupted_tests():
    assert repo_tests.parse_gotest(GO_STREAM) == {
        "m/pkg::TestA": "pass",
        "m/pkg::TestB": "fail",
        "m/pkg::TestC": "skip",
        "m/pkg::TestHung": "error",
    }


def test_go_output_without_json_is_an_error():
    with pytest.raises(ValueError, match="no JSON"):
        repo_tests.parse_gotest("# m/pkg\npkg/a.go:3:1: syntax error\n")


def test_go_package_events_alone_are_valid_and_empty():
    assert repo_tests.parse_gotest('{"Action":"fail","Package":"m/pkg"}\n') == {}


def test_compare_counts_regressions_missing_tests_and_new_passes():
    start = {"a": "pass", "b": "pass", "c": "pass", "d": "fail", "e": "skip", "f": "pass"}
    patched = {"a": "pass", "b": "fail", "d": "pass", "e": "pass", "f": "skip", "g": "pass"}
    assert repo_tests.compare(start, patched) == {"passing_at_start": 4, "regressed": 2, "newly_passing": 3}


def test_compare_counts_an_errored_test_as_regressed():
    assert repo_tests.compare({"a": "pass"}, {"a": "error"})["regressed"] == 1


def test_report_ok_validates_against_the_schema():
    sel = repo_tests.select(["pkg/foo.py"], ["tests/test_foo.py"])
    obj = repo_tests.repo_tests_object(sel, {"a": "pass"}, {"a": "fail"}, 12.34)
    assert obj == {"status": "ok", "selected": ["tests/test_foo.py"], "passing_at_start": 1, "regressed": 1,
                   "newly_passing": 0, "seconds": 12.3}
    PROXIES.validate({"repo_tests": obj})


def test_report_without_selection_is_no_tests():
    obj = repo_tests.repo_tests_object({"selected": []}, {}, {}, 1.0)
    assert obj == {"status": "no_tests", "selected": []}
    PROXIES.validate({"repo_tests": obj})


def test_report_error_keeps_the_selection():
    sel = repo_tests.select(["pkg/foo.py"], ["tests/test_foo.py"])
    for obj in (repo_tests.repo_tests_object(sel, error=True, seconds=900), repo_tests.repo_tests_object(sel)):
        assert obj["status"] == "error"
        assert obj["selected"] == ["tests/test_foo.py"]
        assert "regressed" not in obj
        PROXIES.validate({"repo_tests": obj})


CHECK = {
    "task_id": "t", "dataset": "swebench_pro", "author": "m", "inputs": ["instruction", "start_repo"],
    "files": ["tests/accept/test_x.py"], "command": "python -m pytest tests/accept", "frozen_at": "2026-10-24T00:00:00Z",
}


def test_check_returns_files_command_and_sha_of_the_raw_text():
    text = json.dumps(CHECK, indent=1)
    got = repo_tests.load_check(text)
    assert got == {"files": ["tests/accept/test_x.py"], "command": "python -m pytest tests/accept",
                   "sha256": hashlib.sha256(text.encode()).hexdigest()}


@pytest.mark.parametrize("change", [
    {"files": []}, {"files": ["/etc/passwd"]}, {"files": ["a/../../b"]}, {"files": [""]}, {"command": " "}, {"command": None},
])
def test_check_refuses_bad_files_and_commands(change):
    with pytest.raises(ValueError):
        repo_tests.load_check(json.dumps({**CHECK, **change}))


def test_check_refuses_non_json():
    with pytest.raises(ValueError, match="does not parse"):
        repo_tests.load_check("{")


def test_acceptance_object_validates_and_merge_adds_it(tmp_path):
    acc = repo_tests.acceptance_object("a" * 64, "fail", "pass", 3.14)
    assert acc == {"status": "pass", "at_start": "fail", "check_sha256": "a" * 64, "seconds": 3.1}
    PROXIES.validate({"repo_tests": {"status": "no_tests", "selected": []}, "acceptance": acc})


def test_cli_select_parse_compare_report_merge_round_trip(tmp_path, capsys):
    (tmp_path / "patch.diff").write_text(PATCH)
    (tmp_path / "tree.txt").write_text("pkg/foo.py\ntests/test_foo.py\n")
    (tmp_path / "junit.xml").write_text(JUNIT)
    (tmp_path / "go.json").write_text(GO_STREAM)

    def run(*argv):
        assert repo_tests.main(list(argv)) == 0
        return json.loads(capsys.readouterr().out)

    sel = run("select", "--patch", str(tmp_path / "patch.diff"), "--tree", str(tmp_path / "tree.txt"))
    assert sel["selected"] == ["tests/test_foo.py"]
    (tmp_path / "sel.json").write_text(json.dumps(sel))
    start = run("parse", "--junit", str(tmp_path / "junit.xml"), "--go", str(tmp_path / "go.json"))
    assert len(start) == 9
    (tmp_path / "start.json").write_text(json.dumps(start))
    (tmp_path / "patched.json").write_text(json.dumps({k: v for k, v in start.items() if "test_pass" not in k}))
    assert run("compare", str(tmp_path / "start.json"), str(tmp_path / "patched.json"))["regressed"] == 1
    rt = run("report", "--selection", str(tmp_path / "sel.json"), "--start", str(tmp_path / "start.json"),
             "--patched", str(tmp_path / "patched.json"), "--seconds", "5")
    (tmp_path / "rt.json").write_text(json.dumps(rt))
    merged = run("merge", "--repo-tests", str(tmp_path / "rt.json"))
    assert merged == {"repo_tests": rt}
    PROXIES.validate(merged)


def test_cli_failure_exits_1_with_one_line_on_stderr(tmp_path, capsys):
    (tmp_path / "bad.xml").write_text("not xml")
    assert repo_tests.main(["parse", "--junit", str(tmp_path / "bad.xml")]) == 1
    err = capsys.readouterr().err
    assert err.startswith("repo_tests: ") and err.count("\n") == 1
    assert repo_tests.main(["parse", "--junit", str(tmp_path / "missing.xml")]) == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
