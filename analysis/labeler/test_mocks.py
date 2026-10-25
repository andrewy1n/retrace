"""Label the mock sessions and compare each with mock/expected.json.

  python analysis/labeler/test_mocks.py [MOCK_DIR]

Without MOCK_DIR it builds fresh mocks in a temp dir (about a minute on
Windows). With MOCK_DIR it reuses mocks that make_mock.py built there.
Exits non-zero on any mismatch or missing session.
"""

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "mock"))

import make_mock  # noqa: E402
from rules import label  # noqa: E402
from session import load_session  # noqa: E402


def check(mocks):
    expected = json.loads((HERE / "mock" / "expected.json").read_text())
    keys = ("hard_signals", "failure_type", "suspected_tool_call_id", "features")
    bad = 0
    for sid, want in expected.items():
        try:
            got = label(load_session(sid, mocks / "traces", mocks / "results", mocks / "sessions", mocks / "tasks",
                                     primitives_dir=mocks / "primitives"))
        except FileNotFoundError:
            print(f"MISSING {sid}")
            bad += 1
            continue
        mismatched = [
            k for k in keys
            if (sorted(got[k]) if k == "hard_signals" else got[k])
            != (sorted(want[k]) if k == "hard_signals" else want[k])
        ]
        if mismatched:
            bad += 1
            print(f"BAD {sid}")
            for k in mismatched:
                print(f"    {k}: got {got[k]!r}, want {want[k]!r}")
        else:
            print(f"OK  {sid}")
    print(f"{len(expected) - bad} of {len(expected)} match")
    return bad


def main():
    if len(sys.argv) > 1:
        return 1 if check(Path(sys.argv[1]).resolve()) else 0
    with tempfile.TemporaryDirectory(prefix="retrace-mock-", ignore_cleanup_errors=True) as tmp:
        print(f"Building {len(make_mock.SESSIONS)} mock sessions (about 30 to 60 seconds)...", flush=True)
        make_mock.build(Path(tmp))
        return 1 if check(Path(tmp)) else 0


if __name__ == "__main__":
    sys.exit(main())
