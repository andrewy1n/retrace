#!/usr/bin/env bash
# Run a replay job on the worker from any machine with SSH access to it, and pull the results back.
#
# Usage: recorder/worker/remote.sh submit <job.json> [-d] [parallel=4]
#        recorder/worker/remote.sh fetch <job-id>
#        recorder/worker/remote.sh status
#        recorder/worker/remote.sh install
# submit  validates the job, copies it (and contracts/ and a candidate directory) to the worker, runs run_job.sh and grade.sh in
#         tmux session job-<job-id>, waits, then fetches. -d returns after the start; fetch later. Each result records this
#         checkout's HEAD as repo_sha, so contracts/ and the candidate directory must have no uncommitted changes.
# fetch   copies runs/results/<job-id>/, runs/primitives/<job-id>-*.json, and runs/traces/<job-id>-*.json from the worker
#         into this repo and prints one line per result.
# status  lists the running job sessions and the last log line of each.
# install copies the runner scripts and capture/primitives.py from this checkout to /opt/retrace on the worker. Do it only when no job runs.
# Needs: ssh access to root@<vm_host> (retrace.local.json, gitignored), jq, rsync, Python with jsonschema.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOST="$(jq -re .vm_host "$ROOT/retrace.local.json")" || { echo "Set vm_host in $ROOT/retrace.local.json" >&2; exit 1; }
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
remote() { ssh "${SSH_OPTS[@]}" "root@$HOST" "$@"; }
WREPO=/opt/retrace/repo

fetch() {
  local id="$1"
  mkdir -p "$ROOT/runs/results/$id"
  rsync -a -e "ssh ${SSH_OPTS[*]}" "root@$HOST:$WREPO/runs/results/$id/" "$ROOT/runs/results/$id/"
  local kind
  for kind in primitives traces; do
    mkdir -p "$ROOT/runs/$kind"
    rsync -a -e "ssh ${SSH_OPTS[*]}" --include="$id-*.json" --exclude='*' "root@$HOST:$WREPO/runs/$kind/" "$ROOT/runs/$kind/" \
      || echo "warning: could not fetch runs/$kind for $id" >&2
  done
  jq -r '[.task_id[0:48], (.tool_call_id // "step0"), .arm, .trial, (if .passed == null then "-" elif .passed then "pass" else "FAIL" end), (.proxies.acceptance.status // "-"), (.proxies.repo_tests.regressed // "-"), .cost_credits] | @tsv' \
    "$ROOT/runs/results/$id"/*.json
  jq -s '"results \(length), passed \(map(select(.passed)) | length), credits \(map(.cost_credits) | add)"' -r "$ROOT/runs/results/$id"/*.json
}

submit() {
  local job="$1" detach="$2" par="$3" id arm path="" sid sha dirty
  RETRACE_REPO="$ROOT" RETRACE_ROOT="$ROOT" python3 "$ROOT/recorder/worker/scripts/retrace_job.py" validate "$job"
  id="$(jq -r .job_id "$job")"; arm="$(jq -r .arm.kind "$job")"
  [[ "$arm" != candidate ]] || path="$(jq -r .arm.path "$job")"
  sha="$(git -C "$ROOT" rev-parse HEAD)"
  dirty="$(git -C "$ROOT" status --porcelain -- contracts ${path:+"$path"})"
  [[ -z "$dirty" ]] || { printf 'Commit these first, so repo_sha %s holds what runs:\n%s\n' "$sha" "$dirty" >&2; exit 1; }
  if remote "tmux has-session -t job-$id" 2>/dev/null; then echo "job-$id is already running" >&2; exit 1; fi
  if [[ "$(jq -r .start "$job")" == checkpoint ]]; then
    sid="$(jq -r .session_id "$job")"
    remote "test -d /opt/retrace/sessions/$sid && test -f $WREPO/runs/traces/$sid.json" \
      || { echo "The worker has no recorded session or trace for $sid" >&2; exit 1; }
  fi
  if [[ "$arm" == candidate ]]; then
    [[ -d "$ROOT/$path" ]] || { echo "$ROOT/$path does not exist" >&2; exit 1; }
    remote "mkdir -p $WREPO/$path"
    rsync -a --delete -e "ssh ${SSH_OPTS[*]}" "$ROOT/$path/" "root@$HOST:$WREPO/$path/"
  fi
  rsync -a -e "ssh ${SSH_OPTS[*]}" "$ROOT/contracts/" "root@$HOST:$WREPO/contracts/"
  scp -q "${SSH_OPTS[@]}" "$job" "root@$HOST:$WREPO/runs/jobs/$id.json"
  remote "mkdir -p /opt/retrace/runs/$id && echo $sha > /opt/retrace/runs/$id/repo_sha"
  remote "mkdir -p /root/jobs && tmux new-session -d -s job-$id 'set -a; . /root/.retrace.env; set +a; \
    /opt/retrace/run_job.sh $WREPO/runs/jobs/$id.json $par > /root/jobs/$id.log 2>&1; echo \$? > /root/jobs/$id.run-exit; \
    /opt/retrace/grade.sh $WREPO/runs/jobs/$id.json $par >> /root/jobs/$id.log 2>&1; echo \$? > /root/jobs/$id.grade-exit'"
  echo "started job-$id on the worker (log /root/jobs/$id.log)"
  [[ "$detach" == 0 ]] || { echo "fetch later: recorder/worker/remote.sh fetch $id"; return; }
  while remote "tmux has-session -t job-$id" 2>/dev/null; do sleep 20; done
  echo "run exit $(remote "cat /root/jobs/$id.run-exit"), grade exit $(remote "cat /root/jobs/$id.grade-exit")"
  remote "grep -E 'FAILED|trial failed|skipped, budget|spent ' /root/jobs/$id.log | cut -c1-200" || true
  fetch "$id"
}

case "${1:-}" in
  submit)
    [[ $# -ge 2 ]] || { sed -n '2,6p' "$0"; exit 1; }
    job="$(realpath "$2")"; shift 2; detach=0; par=4
    for a in "$@"; do [[ "$a" == -d ]] && detach=1 || par="$a"; done
    submit "$job" "$detach" "$par" ;;
  fetch) [[ $# -eq 2 ]] || { sed -n '2,6p' "$0"; exit 1; }; fetch "$2" ;;
  status) remote 'for s in $(tmux ls -F "#S" 2>/dev/null | grep ^job-); do echo "$s: $(tail -n 1 /root/jobs/${s#job-}.log | cut -c1-160)"; done' ;;
  install)
    scp -q "${SSH_OPTS[@]}" "$ROOT"/recorder/worker/scripts/{run_job.sh,grade.sh,run_trial.sh,grade_pro.sh,pro_task.sh,prepull.sh,retrace_job.py,tiger_sink.py,proxies.sh,repo_tests.py} "root@$HOST:/opt/retrace/"
    scp -q "${SSH_OPTS[@]}" "$ROOT"/recorder/capture/primitives.py "root@$HOST:/opt/retrace/capture/"
    scp -q "${SSH_OPTS[@]}" "$ROOT"/recorder/replay/{run_checkpoint.sh,docker-droid.sh,restore.sh,fork.mjs} "root@$HOST:/opt/retrace/replay/"
    echo "installed" ;;
  *) sed -n '2,16p' "$0"; exit 1 ;;
esac
