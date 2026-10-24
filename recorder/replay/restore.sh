#!/usr/bin/env bash
# Usage: restore.sh <snapshot-ref> [repo-dir]
# Makes the working tree, index, and HEAD match the moment snapshot.sh ran.
set -euo pipefail

snapshot=$1
cd "${2:-.}"
git cat-file -e "$snapshot^{commit}"

git read-tree -u --reset "$snapshot^{tree}"
# Ignored files stay: SWE-bench images keep build outputs the tests need there.
git clean -fdq

if parent=$(git rev-parse --verify -q "$snapshot^"); then
  git reset -q --mixed "$parent"
fi
