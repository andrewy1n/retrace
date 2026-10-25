#!/usr/bin/env bash
# Start the held-out and regression jobs that make_jobs.py wrote, without overloading the worker.
#
# Usage: recorder/replay/run_final.sh <prefix> [--together]
# Default: held-out a, b, c start at once with 3, 3, 2 trials in flight (8 in all). When all have finished and
#   graded, regression a and c start with 4 each. Without a held-out b job, held-out a and c start with 4 each.
# --together: all jobs start at once with 2, 2, 2, 1, 1 in flight (2, 2, 2, 2 without held-out b).
# Before it starts anything, it checks that the job files, contracts/, and the overlay directories are committed and
# that no job with this prefix runs. Run it in tmux: it waits between the two stages. Fetch with
# recorder/worker/remote.sh fetch <job-id> when a job ends.
set -euo pipefail

[[ $# -ge 1 && $# -le 2 ]] || { sed -n '2,10p' "$0"; exit 1; }
PREFIX="$1"; TOGETHER=0
[[ "${2:-}" != --together ]] || TOGETHER=1
[[ -z "${2:-}" || $TOGETHER -eq 1 ]] || { sed -n '2,10p' "$0"; exit 1; }

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REMOTE="${RETRACE_REMOTE:-$ROOT/recorder/worker/remote.sh}"
POLL="${RETRACE_POLL_S:-60}"
HELD=("$PREFIX-heldout-a" "$PREFIX-heldout-c")
if [[ -f "$ROOT/runs/jobs/$PREFIX-heldout-b.json" ]]; then
  HELD=("$PREFIX-heldout-a" "$PREFIX-heldout-b" "$PREFIX-heldout-c")
fi
REGR=("$PREFIX-regression-a" "$PREFIX-regression-c")

for id in "${HELD[@]}" "${REGR[@]}"; do
  job="$ROOT/runs/jobs/$id.json"
  [[ -f "$job" ]] || { echo "missing $job" >&2; exit 1; }
  paths=("runs/jobs/$id.json" contracts)
  [[ "$(jq -r .arm.kind "$job")" != candidate ]] || paths+=("$(jq -r .arm.path "$job")")
  git -C "$ROOT" ls-files --error-unmatch "${paths[@]}" >/dev/null
  dirty="$(git -C "$ROOT" status --porcelain -- "${paths[@]}")"
  [[ -z "$dirty" ]] || { printf 'Commit these first:\n%s\n' "$dirty" >&2; exit 1; }
done

status="$("$REMOTE" status)"
if grep -q "^job-$PREFIX-" <<<"$status"; then
  echo "jobs with prefix $PREFIX already run:" >&2; grep "^job-$PREFIX-" <<<"$status" >&2; exit 1
fi

submit() { "$REMOTE" submit "$ROOT/runs/jobs/$1.json" -d "$2"; }

if [[ $TOGETHER -eq 1 ]]; then
  reg=2; [[ ${#HELD[@]} -eq 3 ]] && reg=1
  for id in "${HELD[@]}"; do submit "$id" 2; done
  for id in "${REGR[@]}"; do submit "$id" "$reg"; done
  echo "all $((${#HELD[@]} + ${#REGR[@]})) jobs started"
  exit 0
fi

if [[ ${#HELD[@]} -eq 3 ]]; then
  submit "${HELD[0]}" 3; submit "${HELD[1]}" 3; submit "${HELD[2]}" 2
else
  submit "${HELD[0]}" 4; submit "${HELD[1]}" 4
fi
echo "held-out started; waiting to start regression"
while :; do
  if status="$("$REMOTE" status)"; then
    grep -q "^job-$PREFIX-heldout-" <<<"$status" || break
  fi
  sleep "$POLL"
done
submit "${REGR[0]}" 4; submit "${REGR[1]}" 4
echo "regression started"
