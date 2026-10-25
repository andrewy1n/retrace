#!/usr/bin/env bash
# Finish a job and write one result file per trial. A step0 job gets the dataset grader plus proxies. A checkpoint job
# gets proxies only and is never graded. A swebench_verified job (default) goes through the official SWE-bench harness.
# A swebench_pro job goes through the task's own verifier from the SWE-bench Pro harness (grade_pro.sh), one fresh
# container per trial, <max_workers> at once. proxies.sh writes proxies.json in each trial directory.
#
# Usage: /opt/retrace/grade.sh <job.json> [max_workers=8] [trial]
# Results: $RETRACE_REPO/runs/results/<job_id>/<task_id>-<step0 or tool_call_id>-<arm>-<trial>.json
# A step0 trial also gets $RETRACE_REPO/runs/primitives/<job_id>-<task_id>-<trial>.json (capture/primitives.py), upserted to
# Tiger when TIGER_DATABASE_URL is set. A failed extraction prints a warning and sets exit code 1, and keeps the results.
# A checkpoint trial gets no primitives: its transcript holds the copied prefix and no session id names it.
# The harness takes one prediction per instance. A step0 job grades each trial number as one evaluation run.
# A checkpoint job runs proxies.sh for each (tool_call_id, trial), <max_workers> at once.
set -euo pipefail

[[ $# -ge 1 ]] || { sed -n '2,11p' "$0"; exit 1; }
JOB="$(realpath "$1")"; WORKERS="${2:-8}"; ONLY="${3:-}"
ROOT="${RETRACE_ROOT:-/opt/retrace}"
PY="$ROOT/venv/bin/python"

"$PY" "$ROOT/retrace_job.py" validate "$JOB"
JOB_ID="$(jq -r .job_id "$JOB")"
SUITE="$(jq -r '.dataset // "swebench_verified"' "$JOB")"
REPO="${RETRACE_REPO:-$ROOT/repo}"
RUNS="$ROOT/runs/$JOB_ID"
failed=0

primitives_trial() {
  local t="$1" task sids=() out="$REPO/runs/primitives" sid
  for task in $(jq -r '.task_ids[]' "$JOB"); do
    [[ -f "$RUNS/$task/$t/meta.json" ]] && ! jq -e .failed "$RUNS/$task/$t/meta.json" >/dev/null || continue
    sid="$JOB_ID-$task-$t"
    if RETRACE_REPO="$REPO" "$PY" "$ROOT/capture/primitives.py" --sessions "$ROOT/sessions" --out "$out" --session "$sid" >/dev/null; then
      sids+=("$out/$sid.json")
    else
      echo "warning: no primitives for $sid" >&2; failed=1
    fi
  done
  if [[ ${#sids[@]} -gt 0 && -n "${TIGER_DATABASE_URL:-}" ]]; then
    "$PY" "$ROOT/tiger_sink.py" primitives "${sids[@]}" || failed=1
  fi
}

if [[ "$(jq -r .start "$JOB")" == checkpoint ]]; then
  TASK="$(jq -r .task_id "$REPO/runs/traces/$(jq -r .session_id "$JOB").json")"
  proxies_one() {
    local art="$RUNS/$TASK/$1/$2"
    [[ -f "$art/meta.json" ]] && ! jq -e .failed "$art/meta.json" >/dev/null || return 0
    "$ROOT/proxies.sh" "$JOB" "$TASK" "$art"
  }
  export -f proxies_one
  export RUNS TASK ROOT JOB
  for ((t = 1; t <= $(jq .reruns "$JOB"); t++)); do
    [[ -z "$ONLY" || "$ONLY" == "$t" ]] || continue
    jq -r '.tool_call_ids[]' "$JOB" | xargs -r -P "$WORKERS" -I{} bash -c 'proxies_one "$@"' _ {} "$t" \
      || failed=1
    "$PY" "$ROOT/retrace_job.py" collect "$JOB" "$t" || failed=1
  done
  if [[ -n "${TIGER_DATABASE_URL:-}" ]]; then
    "$PY" "$ROOT/tiger_sink.py" results "$REPO/runs/results/$JOB_ID" || failed=1
  fi
  [[ "$failed" -eq 0 ]] || { echo "some trials could not be collected, see above" >&2; exit 1; }
  exit 0
fi

step0_proxies() {
  local t="$1" task
  for task in $(jq -r '.task_ids[]' "$JOB"); do
    [[ -f "$RUNS/$task/$t/meta.json" ]] && ! jq -e .failed "$RUNS/$task/$t/meta.json" >/dev/null && echo "$task"
  done | xargs -r -P "$WORKERS" -I{} "$ROOT/proxies.sh" "$JOB" {} "$RUNS/{}/$t" || failed=1
}

for ((t = 1; t <= $(jq .reruns "$JOB"); t++)); do
  [[ -z "$ONLY" || "$ONLY" == "$t" ]] || continue
  EVAL_DIR="$RUNS/eval-t$t"
  mkdir -p "$EVAL_DIR"
  if [[ "$SUITE" == swebench_pro ]]; then
    for task in $(jq -r '.task_ids[]' "$JOB"); do
      [[ -f "$RUNS/$task/$t/meta.json" ]] && echo "$task"
    done | xargs -r -P "$WORKERS" -I{} "$ROOT/grade_pro.sh" {} "$RUNS/{}/$t/patch.diff" "$EVAL_DIR/{}" || failed=1
    step0_proxies "$t"
    primitives_trial "$t"
    "$PY" "$ROOT/retrace_job.py" collect "$JOB" "$t" || failed=1
    if [[ -n "${TIGER_DATABASE_URL:-}" ]]; then
      "$PY" "$ROOT/tiger_sink.py" results "$REPO/runs/results/$JOB_ID" || failed=1
    fi
    continue
  fi
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
  step0_proxies "$t"
  primitives_trial "$t"
  "$PY" "$ROOT/retrace_job.py" collect "$JOB" "$t" || { failed=1; continue; }
  if [[ -n "${TIGER_DATABASE_URL:-}" ]]; then
    "$PY" "$ROOT/tiger_sink.py" results "$REPO/runs/results/$JOB_ID" || failed=1
  fi
done
[[ "$failed" -eq 0 ]] || { echo "some trials could not be collected, see above" >&2; exit 1; }
