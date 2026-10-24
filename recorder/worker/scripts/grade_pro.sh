#!/usr/bin/env bash
# Grade one patch on one SWE-bench Pro V2 task with the task's own verifier from the official harness.
#
# Usage: /opt/retrace/grade_pro.sh <task_id> <patch.diff | gold | empty> <out_dir>
# Starts a fresh container from the task image, applies the patch as the harness's patch_replay agent does,
# mounts the task's tests/ at /tests and out_dir at /logs/verifier, and runs `bash /tests/test.sh`.
# The verifier writes reward.txt (1 passed, 0 failed). `gold` applies the task's reference patch and `empty` applies nothing.
# Output: <out_dir>/{apply.log,test.log,seconds,reward.txt,output.json,run-script-stdout.txt,run-script-stderr.txt}
# Exits 1 when the verifier left no reward.txt (image, apply, or timeout trouble). Needs PRO_TASKS (see pro_task.sh).
set -euo pipefail

[[ $# -eq 3 ]] || { sed -n '2,9p' "$0"; exit 1; }
IID="$1"; PATCH="$2"; OUT="$(realpath -m "$3")"
# shellcheck source=pro_task.sh
source "$(dirname "$(realpath "$0")")/pro_task.sh"

TASK="$(pro_task_dir "$IID")"
IMAGE="$(pro_image "$IID")"
case "$PATCH" in
  gold) PATCH="$TASK/solution/gold_patch.diff" ;;
  empty) PATCH="" ;;
esac

NAME="retrace-pro-grade-${IID//[^A-Za-z0-9_.-]/-}"
NAME="${NAME:0:100}-$$"
mkdir -p "$OUT"
rm -f "$OUT/reward.txt" "$OUT/output.json" "$OUT/apply.log" "$OUT/test.log" "$OUT/seconds"

# shellcheck disable=SC2329  # invoked via trap
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

start=$SECONDS
docker run -d --name "$NAME" --platform linux/amd64 \
  -v "$TASK/tests:/tests:ro" -v "$OUT:/logs/verifier" "$IMAGE" sleep infinity >/dev/null

if [[ -s "$PATCH" ]]; then
  docker cp "$PATCH" "$NAME:/tmp/replay.patch"
  docker exec "$NAME" bash -c 'cd /app 2>/dev/null || cd /testbed
    git apply --verbose /tmp/replay.patch || git apply --3way /tmp/replay.patch || patch --fuzz=3 -p1 -i /tmp/replay.patch' \
    > "$OUT/apply.log" 2>&1 || echo "[$IID] patch did not apply, see $OUT/apply.log" >&2
fi

set +e
timeout "$(pro_verifier_timeout "$IID")" docker exec "$NAME" bash /tests/test.sh > "$OUT/test.log" 2>&1
rc=$?
set -e
echo $((SECONDS - start)) > "$OUT/seconds"
[[ -f "$OUT/reward.txt" ]] || { echo "[$IID] verifier exit $rc left no reward.txt" >&2; exit 1; }
echo "[$IID] reward $(<"$OUT/reward.txt") in $(<"$OUT/seconds") s"
