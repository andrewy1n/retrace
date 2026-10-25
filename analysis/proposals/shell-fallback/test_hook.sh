#!/bin/sh
# Run from the repo root: sh analysis/proposals/shell-fallback/test_hook.sh

here=$(cd "$(dirname "$0")" && pwd)
hook="$here/.factory/hooks/shell_fallback.sh"
tmp=$(mktemp -d)
export TMPDIR="$tmp"
fail=0

result() {  # result <file> <text>
  printf '{"type":"message","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_x","content":"%s"}]}}\n' "$2" >> "$1"
}
run() {  # run <session> <tool> <transcript> [tool_input]; prints the exit code
  printf '{"session_id":"%s","transcript_path":"%s","cwd":"/repo","tool_name":"%s","tool_input":%s}' "$1" "$3" "$2" "${4:-{\}}" \
    | sh "$hook" 2>"$tmp/stderr"
  echo $?
}
expect() {  # expect <name> <want> <got>
  if [ "$2" = "$3" ]; then echo "OK   $1"; else echo "FAIL $1: want $2, got $3"; fail=1; fi
}

: > "$tmp/ok"; result "$tmp/ok" "Command failed (exit code: 1)"
expect "ordinary shell error: allowed" 0 "$(run s0 Execute "$tmp/ok" '{"command":"pytest"}')"

: > "$tmp/k1"; result "$tmp/k1" "Error: Command terminated by signal: SIGKILL"
expect "after a kill, foreground shell: blocked" 2 "$(run s1 Execute "$tmp/k1" '{"command":"echo hi"}')"
grep -q '\[shell-fallback\]' "$tmp/stderr" && expect "message names the guardrail" 0 0 || expect "message names the guardrail" 0 1
grep -q 'fireAndForget' "$tmp/stderr" && expect "message names fireAndForget" 0 0 || expect "message names fireAndForget" 0 1
expect "same kill again: allowed" 0 "$(run s1 Execute "$tmp/k1" '{"command":"echo hi"}')"
expect "after a kill, background shell: allowed" 0 "$(run s2 Execute "$tmp/k1" '{"command":"pytest","fireAndForget": true}')"
expect "after a kill, other tool: allowed" 0 "$(run s3 Read "$tmp/k1" '{"file_path":"/repo/a"}')"

result "$tmp/k1" "[shell-fallback] earlier"
expect "kill already answered in transcript: allowed" 0 "$(run s4 Execute "$tmp/k1" '{"command":"ls"}')"
result "$tmp/k1" "Error: Command terminated by signal: SIGKILL"
expect "a second kill: blocked again" 2 "$(run s4 Execute "$tmp/k1" '{"command":"ls"}')"

: > "$tmp/k2"; result "$tmp/k2" "Error: Command terminated by signal: SIGKILL"
for i in 1 2 3; do
  ( printf '{"session_id":"sp","transcript_path":"%s","tool_name":"Execute","tool_input":{"command":"ls"}}' "$tmp/k2" \
      | sh "$hook" 2>/dev/null; echo $? > "$tmp/par$i" ) &
done
wait
expect "3 parallel calls after a kill: one blocked" 1 "$(cat "$tmp"/par1 "$tmp"/par2 "$tmp"/par3 | grep -c '^2$')"

expect "missing transcript: allowed" 0 "$(run sm Execute "$tmp/none.jsonl" '{"command":"ls"}')"
expect "empty input: allowed" 0 "$(printf '' | sh "$hook" 2>/dev/null; echo $?)"
expect "garbage input: allowed" 0 "$(printf 'not json' | sh "$hook" 2>/dev/null; echo $?)"

rm -rf "$tmp"
exit $fail
