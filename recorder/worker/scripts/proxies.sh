#!/usr/bin/env bash
# Compute the proxies of one trial's patch in fresh containers from the task image. The proxies use only what a
# production system has: the repo's own tests (repo_tests) and the task's frozen acceptance check (acceptance).
#
# Usage: /opt/retrace/proxies.sh <job.json> <task_id> <art_dir>
# Reads <art_dir>/patch.diff (may be empty) and <art_dir>/start_commit. Writes <art_dir>/proxies.json, the `proxies`
# object of contracts/replay-result.schema.json. `acceptance` appears when $RETRACE_REPO/runs/acceptance/<task_id>/check.json exists.
# Optional: PROXY_TIMEOUT (seconds per run, default 900), RETRACE_REPO, PRO_TASKS (see pro_task.sh), RETRACE_IMAGE
#        and RETRACE_PLATFORM (as in run_checkpoint.sh).
# The start run of repo_tests and the start run of the acceptance check are cached in
# /opt/retrace/runs/<job_id>/proxy-cache/<task_id>/. Exits 0 once proxies.json is written, even when a proxy has status error.
# It never reads the task's tests/ or solution/, the dataset's test lists, or a gold patch.
set -euo pipefail

[[ $# -eq 3 ]] || { sed -n '2,12p' "$0"; exit 1; }
JOB="$(realpath "$1")"; IID="$2"; ART="$(realpath "$3")"
HERE="$(dirname "$(realpath "$0")")"
ROOT="${RETRACE_ROOT:-/opt/retrace}"
REPO="${RETRACE_REPO:-$ROOT/repo}"
PY="$ROOT/venv/bin/python"
[[ -x "$PY" ]] || PY=python3
TOOL="$HERE/repo_tests.py"
DATASET="${SWEBENCH_DATASET:-SWE-bench/SWE-bench_Verified}"
TIMEOUT="${PROXY_TIMEOUT:-900}"
# shellcheck source=pro_task.sh
source "$HERE/pro_task.sh"

[[ -f "$JOB" ]] || { echo "[$IID] no job file $JOB" >&2; exit 1; }
[[ -f "$ART/start_commit" ]] || { echo "[$IID] no start_commit in $ART" >&2; exit 1; }
START="$(<"$ART/start_commit")"
JOB_ID="$(jq -r .job_id "$JOB")"
SUITE="$(jq -r '.dataset // "swebench_verified"' "$JOB")"

WORK="$(mktemp -d)"
CACHE="$ROOT/runs/$JOB_ID/proxy-cache/$IID"
mkdir -p "$CACHE" 2>/dev/null || { CACHE="$WORK/cache"; mkdir -p "$CACHE"; }
PATCH="$ART/patch.diff"
[[ -f "$PATCH" ]] || { : > "$WORK/empty.diff"; PATCH="$WORK/empty.diff"; }

BASE="retrace-proxy-${JOB_ID}-${IID}-$$"
BASE="${BASE//[^A-Za-z0-9_.-]/-}"
BASE="${BASE:0:90}"
BASE="${BASE,,}"
TAGS=(tree start patched accstart accpatched)
# shellcheck disable=SC2329  # invoked via trap
cleanup() {
  for t in "${TAGS[@]}"; do docker rm -f "$BASE-$t" >/dev/null 2>&1 || true; done
  rm -rf "$WORK"
}
trap cleanup EXIT

IMAGE=""
WORKDIR=""
ENVPRE=""
if [[ "$SUITE" != swebench_pro ]]; then
  WORKDIR=/testbed
  ENVPRE='source /opt/miniconda3/bin/activate testbed >/dev/null 2>&1; '
fi
[[ -z "$WORKDIR" && -f "$CACHE/workdir.txt" ]] && WORKDIR="$(<"$CACHE/workdir.txt")"
DEADLINE=0
RUN_SECONDS=0

resolve_image() {
  if [[ -n "${RETRACE_IMAGE:-}" ]]; then
    IMAGE="$RETRACE_IMAGE"
  elif [[ "$SUITE" == swebench_pro ]]; then
    IMAGE="$(pro_image "$IID")" || return 1
  elif [[ -s "$CACHE/image.txt" ]]; then
    IMAGE="$(<"$CACHE/image.txt")"
  else
    IMAGE="$("$PY" - "$DATASET" "$IID" <<'PY'
import sys
from datasets import load_dataset
name, iid = sys.argv[1:3]
print(next(r for r in load_dataset(name, split="test") if r["instance_id"] == iid)["image"])
PY
    )" || return 1
    echo "$IMAGE" > "$CACHE/image.txt"
  fi
  [[ -n "$IMAGE" ]]
}

fresh() {
  local name="$BASE-$1"
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker run -d --name "$name" --platform "${RETRACE_PLATFORM:-linux/amd64}" "$IMAGE" sleep infinity >/dev/null || return 1
  if [[ -z "$WORKDIR" ]]; then
    WORKDIR="$(pro_workdir "$name")"
    [[ -n "$WORKDIR" ]] || return 1
    echo "$WORKDIR" > "$CACHE/workdir.txt"
  fi
}

drop() { docker rm -f "$BASE-$1" >/dev/null 2>&1 || true; }

run_limited() {
  local left=$((DEADLINE - SECONDS))
  (( left > 0 )) || return 124
  timeout "$left" "$@"
}

apply_patch() {
  [[ -s "$PATCH" ]] || return 0
  docker cp "$PATCH" "$1:/tmp/replay.patch" >/dev/null || return 1
  docker exec -w "$WORKDIR" "$1" bash -c 'git apply --verbose /tmp/replay.patch || git apply --3way /tmp/replay.patch || patch --fuzz=3 -p1 -i /tmp/replay.patch' \
    > "$WORK/apply-${1##*-}.log" 2>&1
}

restore_tests() {
  docker exec -w "$WORKDIR" "$1" git checkout "$START" -- "${RESTORE[@]}" || return 1
  (( ${#GO_DIRS[@]} )) || return 0
  docker exec -w "$WORKDIR" "$1" bash -c 'start=$1; shift; shopt -s nullglob
    for d; do for f in "$d"/*_test.go; do f="${f#./}"; git cat-file -e "$start:$f" 2>/dev/null || rm -f "$f"; done; done' _ "$START" "${GO_DIRS[@]}"
}

list_tree() {
  local tree="$CACHE/tree-$START.txt"
  [[ -s "$tree" ]] || {
    fresh tree || return 1
    docker exec -w "$WORKDIR" "$BASE-tree" git -c core.quotePath=false ls-tree -r --name-only "$START" > "$tree.$$" || return 1
    drop tree
    mv "$tree.$$" "$tree"
  }
  TREE="$tree"
}

# Runs the selected tests in a fresh container and writes their outcomes to $3. Mode patched applies the patch first.
test_run() {
  local tag="$1" mode="$2" out="$3" c="$BASE-$1" rc=0 t0=$SECONDS i=0 row
  local parse=()
  mkdir -p "$out"
  DEADLINE=$((SECONDS + TIMEOUT))
  fresh "$tag" || return 1
  docker exec -w "$WORKDIR" "$c" git cat-file -e "$START^{commit}" || return 1
  if [[ "$mode" == patched ]]; then
    apply_patch "$c" || return 1
    restore_tests "$c" || return 1
  fi
  if (( ${#PY_FILES[@]} )); then
    run_limited docker exec -w "$WORKDIR" "$c" bash -c "$ENVPRE"'py=$(command -v python || command -v python3)
      exec "$py" -m pytest -p no:cacheprovider -q --junitxml=/tmp/junit.xml "$@"' _ "${PY_FILES[@]}" \
      > "$out/pytest.log" 2>&1 || rc=$?
    [[ "$rc" -ne 124 ]] || { drop "$tag"; return 1; }
    docker cp "$c:/tmp/junit.xml" "$out/junit.xml" >/dev/null 2>&1 || true
    parse+=(--junit "$out/junit.xml")
  fi
  for row in "${GO_ROWS[@]}"; do
    mapfile -t pkgs < <(jq -r '.pkgs[]' <<< "$row")
    rc=0
    run_limited docker exec -w "$WORKDIR/$(jq -r .module <<< "$row")" "$c" bash -c \
      'go test -json -count=1 "$@" > "/tmp/go-'"$i"'.json" 2> "/tmp/go-'"$i"'.err"' _ "${pkgs[@]}" || rc=$?
    [[ "$rc" -ne 124 ]] || { drop "$tag"; return 1; }
    docker cp "$c:/tmp/go-$i.json" "$out/go-$i.json" >/dev/null 2>&1 || true
    parse+=(--go "$out/go-$i.json")
    i=$((i + 1))
  done
  drop "$tag"
  "$PY" "$TOOL" parse "${parse[@]}" > "$out/outcomes.json" || return 1
  RUN_SECONDS=$((SECONDS - t0))
}

write_repo_tests() {
  "$PY" "$TOOL" report --selection "$WORK/selection.json" "$@" > "$RT_JSON.tmp" && mv "$RT_JSON.tmp" "$RT_JSON"
}

repo_tests_proxy() {
  local cached="" patched_seconds=0 start_seconds=0
  resolve_image || return 1
  list_tree || return 1
  "$PY" "$TOOL" select --patch "$PATCH" --tree "$TREE" > "$WORK/selection.json" || return 1
  if [[ "$(jq '.selected | length' "$WORK/selection.json")" -eq 0 ]]; then
    write_repo_tests
    return 0
  fi
  mapfile -t PY_FILES < <(jq -r '.python[]' "$WORK/selection.json")
  mapfile -t GO_DIRS < <(jq -r '.go_dirs[]' "$WORK/selection.json")
  mapfile -t GO_ROWS < <(jq -c '.go_runs[]' "$WORK/selection.json")
  mapfile -t RESTORE < <(jq -r '.restore[]' "$WORK/selection.json")
  cached="$CACHE/$(jq -r .key "$WORK/selection.json").json"
  # Any failure below leaves the default error result.
  write_repo_tests --error

  if [[ -f "$cached" ]]; then
    jq .outcomes "$cached" > "$WORK/start.json"
    start_seconds="$(jq .seconds "$cached")"
  else
    test_run start start "$WORK/start" || return 1
    start_seconds="$RUN_SECONDS"
    cp "$WORK/start/outcomes.json" "$WORK/start.json"
    jq -n --slurpfile o "$WORK/start.json" --argjson s "$start_seconds" '{outcomes: $o[0], seconds: $s}' > "$cached.$$"
    mv "$cached.$$" "$cached"
  fi

  if [[ -s "$PATCH" ]]; then
    test_run patched patched "$WORK/patched" || return 1
    patched_seconds="$RUN_SECONDS"
    cp "$WORK/patched/outcomes.json" "$WORK/patched.json"
  else
    cp "$WORK/start.json" "$WORK/patched.json"
  fi
  write_repo_tests --start "$WORK/start.json" --patched "$WORK/patched.json" --seconds "$((start_seconds + patched_seconds))"
}

# Sets ACC_STATUS to pass, fail, or error. Mode patched applies the patch before the check files are written.
acceptance_run() {
  local tag="$1" mode="$2" c="$BASE-$1" rc=0 t0=$SECONDS f
  ACC_STATUS=error
  DEADLINE=$((SECONDS + TIMEOUT))
  fresh "$tag" || return 0
  docker exec -w "$WORKDIR" "$c" git cat-file -e "$START^{commit}" || return 0
  if [[ "$mode" == patched ]]; then
    apply_patch "$c" || return 0
  fi
  for f in "${ACC_FILES[@]}"; do
    docker exec "$c" mkdir -p "$(dirname "$WORKDIR/$f")" || return 0
    docker cp "$ACC_DIR/files/$f" "$c:$WORKDIR/$f" >/dev/null || return 0
  done
  docker cp "$WORK/acceptance.sh" "$c:/tmp/acceptance.sh" >/dev/null || return 0
  run_limited docker exec -w "$WORKDIR" "$c" bash -c "$ENVPRE"'bash /tmp/acceptance.sh' > "$WORK/acceptance-$tag.log" 2>&1 || rc=$?
  drop "$tag"
  RUN_SECONDS=$((SECONDS - t0))
  case "$rc" in
    0) ACC_STATUS=pass ;;
    124) ACC_STATUS=error ;;
    *) ACC_STATUS=fail ;;
  esac
}

write_acceptance() {
  "$PY" "$TOOL" acceptance --sha "$ACC_SHA" --at-start "$1" --status "$2" ${3:+--seconds "$3"} > "$ACC_JSON"
}

acceptance_proxy() {
  local cached at_start seconds=0 check
  ACC_SHA="$(sha256sum "$ACC_DIR/check.json" | cut -d' ' -f1)"
  write_acceptance error error
  check="$("$PY" "$TOOL" check "$ACC_DIR/check.json")" || return 1
  ACC_SHA="$(jq -r .sha256 <<< "$check")"
  jq -r .command <<< "$check" > "$WORK/acceptance.sh"
  mapfile -t ACC_FILES < <(jq -r '.files[]' <<< "$check")
  write_acceptance error error
  resolve_image || return 1

  cached="$CACHE/acceptance-$ACC_SHA.json"
  if [[ -f "$cached" ]]; then
    at_start="$(jq -r .at_start "$cached")"
    seconds="$(jq .seconds "$cached")"
  else
    acceptance_run accstart start
    at_start="$ACC_STATUS"
    seconds="$RUN_SECONDS"
    [[ "$at_start" == error ]] || jq -n --arg a "$at_start" --argjson s "$seconds" '{at_start: $a, seconds: $s}' > "$cached"
  fi
  acceptance_run accpatched patched
  write_acceptance "$at_start" "$ACC_STATUS" "$((seconds + RUN_SECONDS))"
}

RT_JSON="$WORK/repo_tests.json"
echo '{"status":"error","selected":[]}' > "$RT_JSON"
ACC_DIR="$REPO/runs/acceptance/$IID"
ACC_JSON=""
[[ ! -f "$ACC_DIR/check.json" ]] || ACC_JSON="$WORK/acceptance.json"

repo_tests_proxy || echo "[$IID] repo_tests proxy stopped early" >&2
[[ -z "$ACC_JSON" ]] || acceptance_proxy || echo "[$IID] acceptance proxy stopped early" >&2

"$PY" "$TOOL" merge --repo-tests "$RT_JSON" ${ACC_JSON:+--acceptance "$ACC_JSON"} > "$ART/proxies.json.tmp"
mv "$ART/proxies.json.tmp" "$ART/proxies.json"
echo "[$IID] proxies: repo_tests $(jq -r .repo_tests.status "$ART/proxies.json")${ACC_JSON:+, acceptance $(jq -r .acceptance.status "$ART/proxies.json")}"
