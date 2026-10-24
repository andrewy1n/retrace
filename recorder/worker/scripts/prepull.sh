#!/usr/bin/env bash
# Pre-pull SWE-bench Verified instance images (amd64) for a list of instance IDs.
#
# Usage:
#   /opt/retrace/prepull.sh django__django-11099 sympy__sympy-20590 ...
#   /opt/retrace/prepull.sh -f ids.txt            # one instance_id per line, '#' comments ok
#   PREPULL_JOBS=6 /opt/retrace/prepull.sh -f ids.txt
#
# Image name rule (matches swebench 5.x ImageSpec.name and the `image` column of
# SWE-bench/SWE-bench_Verified): swebench/sweb.eval.x86_64.<id, "__" -> "_1776_", lowercased>:latest
# Each instance image already contains its env layers, so no separate env image pull is needed.
set -euo pipefail

JOBS="${PREPULL_JOBS:-4}"
TAG="${SWEBENCH_IMAGE_TAG:-latest}"
LOG_DIR="${PREPULL_LOG_DIR:-/opt/retrace/logs/prepull}"

usage() { sed -n '2,10p' "$0"; exit 1; }

ids=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--file)
      [[ $# -ge 2 ]] || usage
      while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%%#*}"; line="${line//[[:space:]]/}"
        [[ -n "$line" ]] && ids+=("$line")
      done < "$2"
      shift 2 ;;
    -h|--help) usage ;;
    *) ids+=("$1"); shift ;;
  esac
done
[[ ${#ids[@]} -gt 0 ]] || usage

image_for() {
  local id="$1"
  local key="swebench/sweb.eval.x86_64.${id//__/_1776_}:${TAG}"
  printf '%s\n' "${key,,}"
}

mkdir -p "$LOG_DIR"
list="$(mktemp)"
trap 'rm -f "$list"' EXIT
for id in "${ids[@]}"; do image_for "$id"; done | sort -u > "$list"

echo "Pulling $(wc -l < "$list") image(s) with $JOBS parallel jobs; logs in $LOG_DIR"
export LOG_DIR
# shellcheck disable=SC2016
xargs -a "$list" -P "$JOBS" -I{} bash -c '
  img="$1"; log="$LOG_DIR/$(echo "$img" | tr "/:" "__").log"
  if docker image inspect "$img" >/dev/null 2>&1; then echo "have  $img"; exit 0; fi
  if docker pull --platform linux/amd64 "$img" >"$log" 2>&1; then echo "ok    $img"; else echo "FAIL  $img (see $log)"; exit 1; fi
' _ {} || { echo "Some pulls failed." >&2; exit 1; }

docker system df
