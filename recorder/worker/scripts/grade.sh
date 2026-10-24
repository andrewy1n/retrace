#!/usr/bin/env bash
# Grade a step0 or checkpoint job with the official SWE-bench harness and write one result file per trial.
#
# Usage: /opt/retrace/grade.sh <job.json> [max_workers=8] [trial]
# Results: $RETRACE_REPO/runs/results/<job_id>/<task_id>-<step0 or tool_call_id>-<arm>-<trial>.json
# The harness takes one prediction per instance. A step0 job grades each trial number as one evaluation run.
# A checkpoint job grades each (tool_call_id, trial) as its own run, with max_workers=1, <max_workers> runs at once.
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

if [[ "$(jq -r .start "$JOB")" == checkpoint ]]; then
  TASK="$(jq -r .task_id "$REPO/runs/traces/$(jq -r .session_id "$JOB").json")"
  grade_one() {
    local cp="$1" t="$2" art="$RUNS/$TASK/$1/$2" eval_dir="$RUNS/eval-$1-t$2"
    [[ -f "$art/meta.json" ]] && ! jq -e .failed "$art/meta.json" >/dev/null || return 0
    mkdir -p "$eval_dir"; cd "$eval_dir"
    { cat "$art/pred.json"; echo; } > predictions.jsonl
    [[ -s "$art/patch.diff" ]] || return 0
    "$PY" -m swebench.harness.run_evaluation \
      --dataset_name "${SWEBENCH_DATASET:-SWE-bench/SWE-bench_Verified}" \
      --predictions_path predictions.jsonl --max_workers 1 \
      --run_id "$cp-t$t-$(date +%Y%m%d%H%M%S)" --report_dir "$eval_dir"
  }
  export -f grade_one
  export RUNS TASK PY SWEBENCH_DATASET
  for ((t = 1; t <= $(jq .reruns "$JOB"); t++)); do
    [[ -z "$ONLY" || "$ONLY" == "$t" ]] || continue
    jq -r '.tool_call_ids[]' "$JOB" | xargs -r -P "$WORKERS" -I{} bash -c 'grade_one "$@"' _ {} "$t" \
      || failed=1
    "$PY" "$ROOT/retrace_job.py" collect "$JOB" "$t" || failed=1
  done
  if [[ -n "${TIGER_DATABASE_URL:-}" ]]; then
    "$PY" "$ROOT/tiger_sink.py" results "$REPO/runs/results/$JOB_ID" || failed=1
  fi
  [[ "$failed" -eq 0 ]] || { echo "some trials could not be collected, see above" >&2; exit 1; }
  exit 0
fi

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
