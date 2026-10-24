#!/usr/bin/env bash
# Grade a step0 job with the official SWE-bench harness and write one result file per trial.
#
# Usage: /opt/retrace/grade.sh <job.json> [max_workers=8] [trial]
# Results: $RETRACE_REPO/runs/results/<job_id>/<task_id>-step0-<arm>-<trial>.json
# The harness takes one prediction per instance, so each trial is graded as its own evaluation run.
set -euo pipefail

[[ $# -ge 1 ]] || { sed -n '2,6p' "$0"; exit 1; }
JOB="$(realpath "$1")"; WORKERS="${2:-8}"; ONLY="${3:-}"
ROOT="${RETRACE_ROOT:-/opt/retrace}"
PY="$ROOT/venv/bin/python"

"$PY" "$ROOT/retrace_job.py" validate "$JOB"
JOB_ID="$(jq -r .job_id "$JOB")"
REPO="${RETRACE_REPO:-$ROOT/repo}"
RUNS="$ROOT/runs/$JOB_ID"
failed=0

for ((t = 1; t <= $(jq .reruns "$JOB"); t++)); do
  [[ -z "$ONLY" || "$ONLY" == "$t" ]] || continue
  EVAL_DIR="$RUNS/eval-t$t"
  mkdir -p "$EVAL_DIR"
  PRED="$EVAL_DIR/predictions.jsonl"
  : > "$PRED"
  for task in $(jq -r '.task_ids[]' "$JOB"); do
    if [[ -f "$RUNS/$task/$t/meta.json" ]]; then cat "$RUNS/$task/$t/pred.json" >> "$PRED"; echo >> "$PRED"; fi
  done
  [[ -s "$PRED" ]] || { echo "trial $t: nothing to grade"; continue; }

  cd "$EVAL_DIR"   # swebench writes logs/run_evaluation/<eval_id>/ under cwd
  "$PY" -m swebench.harness.run_evaluation \
    --dataset_name "${SWEBENCH_DATASET:-SWE-bench/SWE-bench_Verified}" \
    --predictions_path "$PRED" \
    --max_workers "$WORKERS" \
    --run_id "t$t-$(date +%Y%m%d%H%M%S)" \
    --report_dir "$EVAL_DIR"
  "$PY" "$ROOT/retrace_job.py" collect "$JOB" "$t" || { failed=1; continue; }
  if [[ -n "${TIGER_DATABASE_URL:-}" ]]; then
    "$PY" "$ROOT/tiger_sink.py" results "$REPO/runs/results/$JOB_ID" || failed=1
  fi
done
[[ "$failed" -eq 0 ]] || { echo "some trials could not be collected, see above" >&2; exit 1; }
