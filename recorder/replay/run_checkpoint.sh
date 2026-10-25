#!/usr/bin/env bash
# Run one trial of a checkpoint job: rewind a recorded Droid session to one step and continue it in the task image.
#
# Usage: /opt/retrace/replay/run_checkpoint.sh <job.json> <tool_call_id> <trial>
# Needs: FACTORY_API_KEY. A control or candidate arm sends the job's continuation text. A hint arm sends its hint text.
# Optional: DROID_TIMEOUT (seconds, default 1800), RETRACE_REPO (default /opt/retrace/repo),
#        RETRACE_SESSIONS (recorded sessions, default /opt/retrace/sessions), RETRACE_DROID (default /usr/local/bin/droid).
#        RETRACE_IMAGE and RETRACE_PLATFORM (default linux/amd64) replace the dataset image, for a host with another CPU.
# The fork keeps the messages before the step's assistant message, so the repo is restored to the last snapshot before that message.
# Output: /opt/retrace/runs/<job_id>/<task_id>/<tool_call_id>/<trial>/{continuation.md,start_commit,fork.json,patch.diff,pred.json,
#         meta.json,capture/,factory-sessions/}
set -euo pipefail

[[ $# -eq 3 ]] || { sed -n '2,10p' "$0"; exit 1; }
JOB="$(realpath "$1")"; TCID="$2"; TRIAL="$3"
: "${FACTORY_API_KEY:?Set FACTORY_API_KEY first (export FACTORY_API_KEY=fk-...)}"

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${RETRACE_ROOT:-/opt/retrace}"
REPO="${RETRACE_REPO:-$ROOT/repo}"
PY="$ROOT/venv/bin/python"
DATASET="${SWEBENCH_DATASET:-SWE-bench/SWE-bench_Verified}"
DROID_BIN="${RETRACE_DROID:-/usr/local/bin/droid}"
# shellcheck source=../worker/scripts/pro_task.sh
source "$ROOT/pro_task.sh"

JOB_ID="$(jq -r .job_id "$JOB")"
SUITE="$(jq -r '.dataset // "swebench_verified"' "$JOB")"
MODEL="$(jq -r .model "$JOB")"
ARM="$(jq -r .arm.kind "$JOB")"
CANDIDATE="$(jq -r '.arm.path // ""' "$JOB")"
REPO_SHA="$(cat "$ROOT/runs/$JOB_ID/repo_sha" 2>/dev/null || true)"
SID="$(jq -r .session_id "$JOB")"
TRACE="$REPO/runs/traces/$SID.json"
SESS="${RETRACE_SESSIONS:-$ROOT/sessions}/$SID"

IID="$(jq -r .task_id "$TRACE")"
HSID="$(jq -r .harness_session_id "$TRACE")"
MESSAGE_ID="$(jq -re --arg id "$TCID" '.steps[] | select(.tool_call_id == $id) | .message_id' "$TRACE")"
SNAPSHOT="$(jq -r --arg id "$TCID" '.steps as $s | ($s | map(.tool_call_id) | index($id)) as $i | $s[:$i] | map(select(.message_id != $s[$i].message_id)) | last | .snapshot_ref // ""' "$TRACE")"

if [[ "$ARM" == hint ]]; then
  MESSAGE="$(jq -r .arm.text "$JOB")"
else
  MESSAGE="$(jq -r .continuation "$JOB")"
fi
if [[ "$ARM" == candidate ]]; then
  [[ -d "$REPO/$CANDIDATE/.factory" || -f "$REPO/$CANDIDATE/AGENTS.md" ]] \
    || { echo "[$IID] candidate $CANDIDATE has no .factory/ or AGENTS.md under $REPO" >&2; exit 1; }
fi
for f in snapshots.bundle start_commit factory-sessions; do
  [[ -e "$SESS/$f" ]] || { echo "[$IID] $SESS/$f is missing" >&2; exit 1; }
done

OUT="$ROOT/runs/$JOB_ID/$IID/$TCID/$TRIAL"
NAME="retrace-${JOB_ID}-${IID}-${TCID}-${TRIAL}"
NAME="${NAME//[^A-Za-z0-9_.-]/-}"
NAME="${NAME,,}"
rm -rf "$OUT"; mkdir -p "$OUT/capture"
printf '%s' "$MESSAGE" > "$OUT/continuation.md"
cp "$SESS/start_commit" "$OUT/start_commit"

if [[ "$SUITE" == swebench_pro ]]; then
  WORKDIR=""
  IMAGE="${RETRACE_IMAGE:-$(pro_image "$IID")}"
else
  WORKDIR=/testbed
  IMAGE="${RETRACE_IMAGE:-$("$PY" - "$DATASET" "$IID" <<'PY'
import sys
from datasets import load_dataset
name, iid = sys.argv[1:3]
print(next(r for r in load_dataset(name, split="test") if r["instance_id"] == iid)["image"])
PY
  )}"
fi
echo "[$IID/$TCID#$TRIAL] image $IMAGE"

# shellcheck disable=SC2329  # invoked via trap
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$NAME" --platform "${RETRACE_PLATFORM:-linux/amd64}" \
  -e FACTORY_API_KEY \
  -v "$DROID_BIN:/usr/local/bin/droid:ro" \
  -v "$OUT:/retrace" \
  -v "$ROOT/capture:/opt/retrace-capture:ro" \
  -v "$HERE/restore.sh:/opt/retrace-replay/restore.sh:ro" \
  ${WORKDIR:+-w "$WORKDIR"} "$IMAGE" sleep infinity >/dev/null
[[ -n "$WORKDIR" ]] || WORKDIR="$(pro_workdir "$NAME")"
[[ -n "$WORKDIR" ]] || { echo "[$IID] no git repository in /app or /testbed" >&2; exit 1; }
export RETRACE_WORKDIR="$WORKDIR"

docker exec "$NAME" bash -c "printf '/.factory/\n/AGENTS.md\n' >> $WORKDIR/.git/info/exclude"
if [[ "$ARM" == candidate ]]; then
  [[ -d "$REPO/$CANDIDATE/.factory" ]] && docker cp "$REPO/$CANDIDATE/.factory" "$NAME:$WORKDIR/.factory"
  [[ -f "$REPO/$CANDIDATE/AGENTS.md" ]] && docker cp "$REPO/$CANDIDATE/AGENTS.md" "$NAME:$WORKDIR/AGENTS.md"
fi
docker exec -i "$NAME" bash -c 'mkdir -p /root/.factory/sessions && cat > /root/.factory/hooks.json' <<'JSON'
{"PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "/opt/retrace-capture/hook.sh"}]}]}
JSON
DROID_VERSION="$(docker exec "$NAME" droid --version | tail -n 1)"

# Put the recorded session and its snapshot commits back where the capture run left them.
docker cp "$SESS/factory-sessions/." "$NAME:/root/.factory/sessions/" >/dev/null
docker cp "$SESS/snapshots.bundle" "$NAME:/tmp/snapshots.bundle"
docker exec "$NAME" git -C "$WORKDIR" fetch -q /tmp/snapshots.bundle 'refs/retrace/*:refs/retrace/*'
docker exec "$NAME" git -C "$WORKDIR" cat-file -e "$(<"$OUT/start_commit")^{commit}"

if [[ -n "$SNAPSHOT" ]]; then
  RESTORE_CMD="docker exec -w $WORKDIR $NAME /opt/retrace-replay/restore.sh $SNAPSHOT $WORKDIR"
else
  RESTORE_CMD="docker exec -w $WORKDIR $NAME bash -c 'git reset -q --hard $(<"$OUT/start_commit") && git clean -fdq'"
fi

set +e
RETRACE_CONTAINER="$NAME" timeout "$(( ${DROID_TIMEOUT:-1800} + 120 ))" node "$HERE/fork.mjs" \
  --session-id "$HSID" --message-id "$MESSAGE_ID" --model "$MODEL" --message-file "$OUT/continuation.md" \
  --out "$OUT" --timeout "${DROID_TIMEOUT:-1800}" \
  --restore-cmd "$RESTORE_CMD" \
  > "$OUT/fork.stdout" 2> "$OUT/fork.stderr"
rc=$?
set -e
echo "[$IID/$TCID#$TRIAL] fork exit $rc"

docker exec "$NAME" bash -c "cd $WORKDIR && git add -A && git -c core.fileMode=false diff --cached $(<"$OUT/start_commit")" > "$OUT/patch.diff"
echo "[$IID/$TCID#$TRIAL] patch $(wc -l < "$OUT/patch.diff") lines"

"$PY" - "$IID" "$JOB_ID-$ARM" "$OUT/patch.diff" "$OUT/pred.json" <<'PY'
import json, sys
iid, model, patch, out = sys.argv[1:5]
json.dump({"instance_id": iid, "model_name_or_path": model, "model_patch": open(patch).read()}, open(out, "w"))
PY

docker cp "$NAME:/root/.factory/sessions" "$OUT/factory-sessions" >/dev/null 2>&1 || true

# A trial that did not reach the end of the fork is an infrastructure failure, not a model failure.
FAILED=""
if [[ ! -f "$OUT/fork.json" ]] || ! jq -e '.successor_session_id' "$OUT/fork.json" >/dev/null 2>&1; then
  FAILED="no fork: $(grep -E '^_?[A-Za-z]*Error:' "$OUT/fork.stderr" 2>/dev/null | tail -n 1)"
elif [[ "$rc" -ne 0 && "$rc" -ne 124 ]] || ! jq -e '.timed_out or .success' "$OUT/fork.json" >/dev/null 2>&1; then
  FAILED="fork run ended with exit $rc, subtype $(jq -r '.subtype // "none"' "$OUT/fork.json")"
fi

COST="$(jq -r '.cost_credits // empty' "$OUT/fork.json" 2>/dev/null || true)"
jq -n --arg v "$DROID_VERSION" --argjson cost "${COST:-0}" --argjson rc "$rc" --arg failed "$FAILED" \
  --arg msg "$(<"$OUT/continuation.md")" --arg model "$(jq -r '.model // ""' "$OUT/fork.json" 2>/dev/null || true)" \
  --arg fork "$(jq -r '.successor_session_id // ""' "$OUT/fork.json" 2>/dev/null || true)" \
  --argjson timed_out "$(jq '.timed_out // false' "$OUT/fork.json" 2>/dev/null || echo false)" --arg sha "$REPO_SHA" \
  '{droid_version: $v, cost_credits: $cost, droid_exit: $rc, timed_out: $timed_out, successor_session_id: $fork, continuation: $msg}
   + (if $model != "" then {model: $model} else {} end) + (if $failed != "" then {failed: $failed} else {} end)
   + (if $sha != "" then {repo_sha: $sha} else {} end)' > "$OUT/meta.json"
[[ -z "$FAILED" ]] || { echo "[$IID/$TCID#$TRIAL] FAILED: $FAILED" >&2; exit 1; }
