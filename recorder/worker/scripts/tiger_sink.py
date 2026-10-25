#!/usr/bin/env python3
"""Upsert replay results or primitives into Tiger (Postgres). Needs TIGER_DATABASE_URL.

  tiger_sink.py results <dir>
  tiger_sink.py primitives <dir>
"""
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb
from jsonschema import Draft202012Validator

ROOT = Path(os.environ.get("RETRACE_ROOT", "/opt/retrace"))
REPO = Path(os.environ.get("RETRACE_REPO", ROOT / "repo"))

RESULT_KEY = ("job_id", "task_id", "checkpoint", "arm", "trial")
RESULT_COLUMNS = RESULT_KEY + (
    "session_id", "tool_call_id", "model", "droid_version", "stop_mode",
    "passed", "grader", "evidence_role", "cost_credits", "timed_out", "proxies",
)
SESSION_KEY = ("session_id",)
SESSION_COLUMNS = SESSION_KEY + (
    "task_id", "job_id", "trial", "harness", "assistant_turns", "tool_calls", "timed_out",
    "input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens",
    "thinking_tokens", "factory_credits",
)
CALL_KEY = ("session_id", "tool_call_id")
CALL_COLUMNS = CALL_KEY + (
    "position", "turn", "tool_name", "command_class", "test_runner", "path_arg_count",
    "background", "duration_s", "is_error", "exit_code", "files", "output_chars",
    "output_tokens_est", "turns_after", "repeats_earlier",
)


def schema(name):
    return json.loads((REPO / "contracts" / f"{name}.schema.json").read_text())


def load(path, name):
    instance = json.loads(path.read_text())
    errors = sorted(Draft202012Validator(schema(name)).iter_errors(instance), key=str)
    if errors:
        sys.exit(f"{path}: {name}.schema.json: " + "; ".join(e.message for e in errors))
    return instance


def upsert(table, key, columns):
    sets = ", ".join(f"{c} = excluded.{c}" for c in columns if c not in key)
    return (
        f"insert into {table} ({', '.join(columns)}) "
        f"values ({', '.join(f'%({c})s' for c in columns)}) "
        f"on conflict ({', '.join(key)}) do update set {sets}"
    )


RESULT_SQL = upsert("replay_results", RESULT_KEY, RESULT_COLUMNS)
SESSION_SQL = upsert("primitives_sessions", SESSION_KEY, SESSION_COLUMNS)
CALL_SQL = upsert("primitives_calls", CALL_KEY, CALL_COLUMNS)


def write_result(cur, path):
    result = load(path, "replay-result")
    row = {c: result.get(c) for c in RESULT_COLUMNS}
    row["checkpoint"] = result.get("tool_call_id", "step0")
    if row["proxies"] is not None:
        row["proxies"] = Jsonb(row["proxies"])
    cur.execute(RESULT_SQL, row)


def write_primitives(cur, path):
    primitives = load(path, "primitives")
    flat = {**primitives, **primitives["token_usage"]}
    cur.execute(SESSION_SQL, {c: flat[c] for c in SESSION_COLUMNS})
    for call in primitives["calls"]:
        row = {**call, "session_id": primitives["session_id"]}
        cur.execute(CALL_SQL, {c: row[c] for c in CALL_COLUMNS})


WRITERS = {"results": write_result, "primitives": write_primitives}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in WRITERS:
        sys.exit(__doc__)
    url = os.environ.get("TIGER_DATABASE_URL")
    if not url:
        sys.exit("TIGER_DATABASE_URL is not set")
    kind, folder = sys.argv[1], Path(sys.argv[2])
    files = sorted(folder.rglob("*.json"))
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for path in files:
            WRITERS[kind](cur, path)
    print(f"{kind}: upserted {len(files)} files from {folder}")


main()
