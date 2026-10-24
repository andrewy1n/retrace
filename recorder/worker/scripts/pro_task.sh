#!/usr/bin/env bash
# Sourced by the runners and graders. Reads one SWE-bench Pro V2 task from the official harness checkout.
# PRO_TASKS is <scaleapi/SWE-bench_Pro-os>/v2/tasks. cloud-init clones it at the pinned commit.

PRO_TASKS="${PRO_TASKS:-${RETRACE_ROOT:-/opt/retrace}/swe-bench-pro/v2/tasks}"

pro_task_dir() {
  [[ -d "$PRO_TASKS/$1" ]] || { echo "no SWE-bench Pro task $1 under $PRO_TASKS" >&2; return 1; }
  echo "$PRO_TASKS/$1"
}

pro_image() {
  sed -n 's/^docker_image = "\(.*\)"$/\1/p' "$(pro_task_dir "$1")/task.toml"
}

pro_verifier_timeout() {
  awk '/^\[verifier\]$/ {s = 1; next} /^\[/ {s = 0} s && /^timeout_sec/ {print int($3)}' "$(pro_task_dir "$1")/task.toml"
}

pro_workdir() {
  docker exec "$1" bash -c 'for d in /app /testbed; do [ -d "$d/.git" ] && echo "$d" && break; done'
}
