#!/usr/bin/env bash
# Run every task and rerun of a step0 job. Trials that already have a meta.json are skipped.
#
# Usage: /opt/retrace/run_job.sh <job.json> [parallel=8]
# Stops starting trials once the credits spent reach budget_credits. Running trials finish, so up to
# <parallel> trials can overshoot. Exits 3 when trials are left undone.
# Then grade: /opt/retrace/grade.sh <job.json>
set -euo pipefail

[[ $# -ge 1 ]] || { sed -n '2,7p' "$0"; exit 1; }
JOB="$(realpath "$1")"; PARALLEL="${2:-8}"
ROOT="${RETRACE_ROOT:-/opt/retrace}"
PY="$ROOT/venv/bin/python"

"$PY" "$ROOT/retrace_job.py" validate "$JOB"
JOB_ID="$(jq -r .job_id "$JOB")"
BUDGET="$(jq .budget_credits "$JOB")"
RUNS="$ROOT/runs/$JOB_ID"
mkdir -p "$RUNS"

spent() { find "$RUNS" -name meta.json -exec cat {} + | jq -s '[.[].cost_credits] | add // 0'; }
pairs() {
  for ((t = 1; t <= $(jq .reruns "$JOB"); t++)); do
    for task in $(jq -r '.task_ids[]' "$JOB"); do
      [[ -f "$RUNS/$task/$t/meta.json" ]] || echo "$task $t"
    done
  done
}

worker() {
  if jq -en --argjson s "$(spent)" --argjson b "$BUDGET" '$s >= $b' >/dev/null; then
    echo "[$1#$2] skipped, budget reached"; return 0
  fi
  "$ROOT/run_trial.sh" "$JOB" "$1" "$2" || echo "[$1#$2] run_trial failed" >&2
}
export -f worker spent
export JOB ROOT RUNS BUDGET

pairs | xargs -r -P "$PARALLEL" -L1 bash -c 'worker "$@"' _

left="$(pairs | wc -l)"
echo "spent $(spent) of $BUDGET credits; $left trial(s) left"
[[ "$left" -eq 0 ]] || exit 3
