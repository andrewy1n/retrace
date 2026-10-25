#!/bin/sh
# Run from the repo root: sh analysis/proposals/root-search-limit/test_hook.sh

here=$(cd "$(dirname "$0")" && pwd)
hook="$here/.factory/hooks/root_search_limit.sh"
tmp=$(mktemp -d)
export TMPDIR="$tmp"
export FACTORY_PROJECT_DIR=/repo
fail=0

: > "$tmp/t"
run() {  # run <session> <tool> <tool_input>; prints the exit code
  printf '{"session_id":"%s","transcript_path":"%s","cwd":"/repo","tool_name":"%s","tool_input":%s}' "$1" "$tmp/t" "$2" "$3" \
    | sh "$hook" 2>"$tmp/stderr"
  echo $?
}
expect() {  # expect <name> <want> <got>
  if [ "$2" = "$3" ]; then echo "OK   $1"; else echo "FAIL $1: want $2, got $3"; fail=1; fi
}

expect "content search at the root: blocked" 2 "$(run s1 Grep '{"pattern":"a|b","path":"/repo","output_mode":"content","line_numbers":true}')"
grep -q '\[root-search-limit\]' "$tmp/stderr" && expect "message names the guardrail" 0 0 || expect "message names the guardrail" 0 1
expect "same session again: allowed (fires once)" 0 "$(run s1 Grep '{"pattern":"a","path":"/repo","output_mode":"content"}')"
expect "root with a slash: blocked" 2 "$(run s2 Grep '{"pattern":"a","path":"/repo/","output_mode": "content"}')"
expect "no path: blocked" 2 "$(run s3 Grep '{"pattern":"a","output_mode":"content"}')"
expect "dot path: blocked" 2 "$(run s4 Grep '{"pattern":"a","path":".","output_mode":"content"}')"
expect "root with a glob: blocked" 2 "$(run s5 Grep '{"pattern":"a","path":"/repo","glob_pattern":"*.go","output_mode":"content"}')"
expect "root with head_limit: allowed" 0 "$(run s6 Grep '{"pattern":"a","path":"/repo","output_mode":"content","head_limit":40}')"
expect "root, file_paths mode: allowed" 0 "$(run s7 Grep '{"pattern":"a","path":"/repo","output_mode":"file_paths"}')"
expect "subdirectory: allowed" 0 "$(run s8 Grep '{"pattern":"a","path":"/repo/lib","output_mode":"content"}')"
expect "other tool: allowed" 0 "$(run s9 Read '{"file_path":"/repo"}')"

printf '%s\n' '{"type":"tool_result","content":"[root-search-limit] earlier"}' >> "$tmp/t"
expect "marker in transcript, new container: allowed" 0 "$(run s10 Grep '{"pattern":"a","path":"/repo","output_mode":"content"}')"
: > "$tmp/t"

for i in 1 2 3; do
  ( printf '{"session_id":"sp","transcript_path":"%s","tool_name":"Grep","tool_input":{"pattern":"a","path":"/repo","output_mode":"content"}}' "$tmp/t" \
      | sh "$hook" 2>/dev/null; echo $? > "$tmp/par$i" ) &
done
wait
expect "3 parallel root searches: one blocked" 1 "$(cat "$tmp"/par1 "$tmp"/par2 "$tmp"/par3 | grep -c '^2$')"

expect "empty input: allowed" 0 "$(printf '' | sh "$hook" 2>/dev/null; echo $?)"
expect "garbage input: allowed" 0 "$(printf 'not json' | sh "$hook" 2>/dev/null; echo $?)"

rm -rf "$tmp"
exit $fail
