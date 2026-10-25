#!/bin/sh
# Test explore_budget.sh with fake hook inputs. Run from the repo root:
#   sh analysis/proposals/explore-budget/test_hook.sh
# Not copied onto a task checkout: the runner copies only .factory/ and AGENTS.md.

here=$(cd "$(dirname "$0")" && pwd)
hook="$here/.factory/hooks/explore_budget.sh"
tmp=$(mktemp -d)
export TMPDIR="$tmp"
fail=0

transcript() {  # transcript <file> <tool names...>
  f=$1; shift; : > "$f"; i=0
  for t in "$@"; do
    i=$((i + 1))
    printf '{"type":"message","message":{"content":[{"type":"tool_use","id":"toolu_%s","name":"%s","input":{}}]}}\n' "$i" "$t" >> "$f"
  done
}
run() {  # run <session> <tool> <transcript>; prints the exit code
  printf '{"session_id":"%s","transcript_path":"%s","cwd":"/repo","tool_name":"%s","tool_input":{}}' "$1" "$3" "$2" \
    | sh "$hook" 2>"$tmp/stderr"
  echo $?
}
expect() {  # expect <name> <want> <got>
  if [ "$2" = "$3" ]; then echo "OK   $1"; else echo "FAIL $1: want $2, got $3"; fail=1; fi
}

transcript "$tmp/t9" Grep Read Read Read Read Grep Read Read Read
expect "9 calls, no edit: allowed" 0 "$(run s9 Read "$tmp/t9")"

transcript "$tmp/t10" Grep Read Read Read Read Grep Read Read Read Read
expect "10 calls, no edit: blocked" 2 "$(run s10 Read "$tmp/t10")"
grep -q '\[explore-budget\]' "$tmp/stderr" && expect "message names the guardrail" 0 0 || expect "message names the guardrail" 0 1
expect "same session again: allowed (fires once)" 0 "$(run s10 Read "$tmp/t10")"

printf '%s\n' '{"type":"tool_result","content":"[explore-budget] earlier"}' >> "$tmp/t10"
expect "marker in transcript, new container: allowed" 0 "$(run s10-fork Grep "$tmp/t10")"

transcript "$tmp/tedit" Read Read Edit Read Read Read Read Read Read Read Read Read
expect "edit already made: allowed" 0 "$(run se Read "$tmp/tedit")"

transcript "$tmp/t12" Read Read Read Read Read Read Read Read Read Read Read Read
expect "the edit itself: allowed" 0 "$(run sx Edit "$tmp/t12")"
expect "missing transcript: allowed" 0 "$(run sm Read "$tmp/none.jsonl")"

rm -rf "$tmp"
exit $fail
