#!/usr/bin/env bash
# Run one trial of a step0 job: Droid on one SWE-bench task inside its official image.
# The job's dataset picks the task source: swebench_verified (default, repo at /testbed) or
# swebench_pro (SWE-bench Pro V2: prompt from the harness's instruction.md, repo at /app or /testbed).
#
# Usage: /opt/retrace/run_trial.sh <job.json> <task_id> <trial>
# Needs: FACTORY_API_KEY in the environment. Optional: DROID_TIMEOUT (seconds, default 1800),
#        RETRACE_REPO (default /opt/retrace/repo), PRO_TASKS (see pro_task.sh).
# Output: /opt/retrace/runs/<job_id>/<task_id>/<trial>/{prompt.md,start_commit,droid.json,droid.stderr,patch.diff,pred.json,meta.json,
#         capture/,factory-sessions/,snapshots.bundle}
# Writes the trace to $RETRACE_REPO/runs/traces/<session_id>.json, where session_id is <job_id>-<task_id>-<trial>,
# and links /opt/retrace/sessions/<session_id> to the output directory.
set -euo pipefail

[[ $# -eq 3 ]] || { sed -n '2,9p' "$0"; exit 1; }
JOB="$(realpath "$1")"; IID="$2"; TRIAL="$3"
: "${FACTORY_API_KEY:?Set FACTORY_API_KEY first (export FACTORY_API_KEY=fk-...)}"

ROOT="${RETRACE_ROOT:-/opt/retrace}"
REPO="${RETRACE_REPO:-$ROOT/repo}"
PY="$ROOT/venv/bin/python"
DATASET="${SWEBENCH_DATASET:-SWE-bench/SWE-bench_Verified}"
# shellcheck source=pro_task.sh
source "$ROOT/pro_task.sh"

JOB_ID="$(jq -r .job_id "$JOB")"
SUITE="$(jq -r '.dataset // "swebench_verified"' "$JOB")"
MODEL="$(jq -r .model "$JOB")"
ARM="$(jq -r .arm.kind "$JOB")"
HINT="$(jq -r '.arm.text // ""' "$JOB")"
CANDIDATE="$(jq -r '.arm.path // ""' "$JOB")"

OUT="$ROOT/runs/$JOB_ID/$IID/$TRIAL"
NAME="retrace-${JOB_ID}-${IID}-${TRIAL}"
NAME="${NAME//[^A-Za-z0-9_.-]/-}"
NAME="${NAME,,}"
rm -rf "$OUT"; mkdir -p "$OUT"

if [[ "$ARM" == candidate ]]; then
  [[ -d "$REPO/$CANDIDATE/.factory" || -f "$REPO/$CANDIDATE/AGENTS.md" ]] \
    || { echo "[$IID] candidate $CANDIDATE has no .factory/ or AGENTS.md under $REPO" >&2; exit 1; }
fi

# 1. Prompt: the problem statement, plus the hint for a hint arm. Never tests, patch, or dataset hints.
if [[ "$SUITE" == swebench_pro ]]; then
  WORKDIR=""
  IMAGE="$(pro_image "$IID")"
  cp "$(pro_task_dir "$IID")/instruction.md" "$OUT/prompt.md"
  [[ -z "$HINT" ]] || printf '\n<hint>\n%s\n</hint>\n' "$HINT" >> "$OUT/prompt.md"
else
  WORKDIR=/testbed
  IMAGE="$("$PY" - "$DATASET" "$IID" "$OUT/prompt.md" "$HINT" <<'PY'
import sys
from datasets import load_dataset
name, iid, out, hint = sys.argv[1:5]
row = next(r for r in load_dataset(name, split="test") if r["instance_id"] == iid)
text = (
    "You are working in the git repository at /testbed (Python env: "
    "`source /opt/miniconda3/bin/activate testbed`).\n"
    "Resolve the issue below by editing the source code. Do not commit.\n\n"
    "<issue>\n" + row["problem_statement"] + "\n</issue>\n"
)
if hint:
    text += "\n<hint>\n" + hint + "\n</hint>\n"
open(out, "w").write(text)
print(row["image"])
PY
  )"
fi
echo "[$IID#$TRIAL] image $IMAGE"

# shellcheck disable=SC2329  # invoked via trap
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# 2. Start the task container with the host droid binary mounted read-only.
docker run -d --name "$NAME" --platform linux/amd64 \
  -e FACTORY_API_KEY \
  -v /usr/local/bin/droid:/usr/local/bin/droid:ro \
  -v "$OUT:/retrace" \
  -v "$ROOT/capture:/opt/retrace-capture:ro" \
  ${WORKDIR:+-w "$WORKDIR"} "$IMAGE" sleep infinity >/dev/null
[[ -n "$WORKDIR" ]] || WORKDIR="$(pro_workdir "$NAME")"
[[ -n "$WORKDIR" ]] || { echo "[$IID] no git repository in /app or /testbed" >&2; exit 1; }

# 3. Record HEAD to diff against. Candidate arm: overlay .factory/ and AGENTS.md. Keep both out of the patch.
docker exec "$NAME" bash -c "printf '/.factory/\n/AGENTS.md\n' >> $WORKDIR/.git/info/exclude"
if [[ "$ARM" == candidate ]]; then
  [[ -d "$REPO/$CANDIDATE/.factory" ]] && docker cp "$REPO/$CANDIDATE/.factory" "$NAME:$WORKDIR/.factory"
  [[ -f "$REPO/$CANDIDATE/AGENTS.md" ]] && docker cp "$REPO/$CANDIDATE/AGENTS.md" "$NAME:$WORKDIR/AGENTS.md"
fi
docker exec -i "$NAME" bash -c 'mkdir -p /root/.factory && cat > /root/.factory/hooks.json' <<'JSON'
{"PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "/opt/retrace-capture/hook.sh"}]}]}
JSON
docker exec "$NAME" git -C "$WORKDIR" rev-parse HEAD > "$OUT/start_commit"
DROID_VERSION="$(docker exec "$NAME" droid --version | tail -n 1)"

# 4. Headless Droid run. The container is disposable, so skip permission prompts.
set +e
timeout "${DROID_TIMEOUT:-1800}" docker exec -e FACTORY_API_KEY -e RETRACE_CAPTURE_DIR=/retrace/capture "$NAME" \
  droid exec --skip-permissions-unsafe --cwd "$WORKDIR" -o json --model "$MODEL" -f /retrace/prompt.md \
  > "$OUT/droid.json" 2> "$OUT/droid.stderr"
rc=$?
set -e
echo "[$IID#$TRIAL] droid exit $rc"

# 5. Patch = everything changed since the container started, including new files.
docker exec "$NAME" bash -c "cd $WORKDIR && git add -A && git -c core.fileMode=false diff --cached $(<"$OUT/start_commit")" > "$OUT/patch.diff"
echo "[$IID#$TRIAL] patch $(wc -l < "$OUT/patch.diff") lines"

"$PY" - "$IID" "$JOB_ID-$ARM" "$OUT/patch.diff" "$OUT/pred.json" <<'PY'
import json, sys
iid, model, patch, out = sys.argv[1:5]
json.dump({"instance_id": iid, "model_name_or_path": model, "model_patch": open(patch).read()}, open(out, "w"))
PY

# 6. Trace: keep the Droid session and the snapshot commits, then join them into runs/traces/.
docker cp "$NAME:/root/.factory/sessions" "$OUT/factory-sessions" >/dev/null 2>&1 || true
docker exec -e WORKDIR "$NAME" bash -c 'cd "$WORKDIR" && refs=$(git for-each-ref --format="%(refname)" refs/retrace) && [ -n "$refs" ] && git bundle create /retrace/snapshots.bundle $refs ^$(git rev-parse "$(cat /retrace/start_commit)^")' >/dev/null 2>&1 || true
mkdir -p "$ROOT/sessions" && ln -sfn "$OUT" "$ROOT/sessions/$JOB_ID-$IID-$TRIAL"
TRANSCRIPT="$(find "$OUT/factory-sessions" -name '*.jsonl' 2>/dev/null | head -n 1)"
CAPTURE="$(find "$OUT/capture" -name '*.jsonl' 2>/dev/null | head -n 1)"
if [[ -n "$TRANSCRIPT" && -n "$CAPTURE" ]]; then
  RETRACE_REPO="$REPO" "$PY" "$ROOT/capture/trace.py" --session-id "$JOB_ID-$IID-$TRIAL" --task-id "$IID" \
    --transcript "$TRANSCRIPT" --capture "$CAPTURE" || echo "[$IID#$TRIAL] trace failed" >&2
else
  echo "[$IID#$TRIAL] no transcript or capture log, no trace" >&2
fi

# 7. Cost and metadata. A killed run prints no JSON, so its cost comes from the session's settings.json.
COST="$(jq -r '.usage.factory_credits // empty' "$OUT/droid.json" 2>/dev/null || true)"
if [[ -z "$COST" ]]; then
  SETTINGS="$(find "$OUT/factory-sessions" -name '*.settings.json' 2>/dev/null | head -n 1)"
  if [[ -n "$SETTINGS" ]]; then
    COST="$(jq -r '.tokenUsage.factoryCredits // empty' "$SETTINGS" 2>/dev/null || true)"
  fi
fi
TIMED_OUT=false
[[ "$rc" -ne 124 ]] || TIMED_OUT=true
jq -n --arg v "$DROID_VERSION" --argjson cost "${COST:-0}" --argjson rc "$rc" --argjson timed_out "$TIMED_OUT" \
  --arg sid "$(jq -r '.session_id // ""' "$OUT/droid.json" 2>/dev/null || true)" \
  '{droid_version: $v, cost_credits: $cost, droid_exit: $rc, timed_out: $timed_out, droid_session_id: $sid}' > "$OUT/meta.json"
