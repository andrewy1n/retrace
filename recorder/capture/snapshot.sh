#!/usr/bin/env bash
# Usage: snapshot.sh [repo-dir]
# Prints a commit id for the whole working tree, untracked files included.
set -euo pipefail

cd "${1:-.}"
git_dir=$(git rev-parse --absolute-git-dir)
index=$(mktemp "$git_dir/retrace-index.XXXXXX")
trap 'rm -f "$index"' EXIT

if [[ -f $git_dir/index ]]; then
  cp "$git_dir/index" "$index"
else
  rm -f "$index"
fi

GIT_INDEX_FILE=$index git add -A
tree=$(GIT_INDEX_FILE=$index git write-tree)

parent=()
if head=$(git rev-parse --verify -q HEAD); then
  parent=(-p "$head")
fi

commit=$(git -c user.name=retrace -c user.email=retrace@localhost \
  commit-tree "$tree" "${parent[@]}" -m "retrace snapshot")
git update-ref "refs/retrace/$commit" "$commit"
echo "$commit"
