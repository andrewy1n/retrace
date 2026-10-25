#!/bin/sh
# Run from the repo root: sh analysis/proposals/read-whole-file/test_hook.sh

here=$(cd "$(dirname "$0")" && pwd)
hook="$here/.factory/hooks/read_whole_file.sh"
tmp=$(mktemp -d)
export TMPDIR="$tmp"
fail=0

: > "$tmp/t"
seq 1 300 > "$tmp/small.py"
seq 1 300 > "$tmp/b.py"
seq 1 300 > "$tmp/c.py"
seq 1 300 > "$tmp/d.py"
seq 1 300 > "$tmp/p.py"
seq 1 2000 > "$tmp/big.py"
run() {  # run <session> <tool> <tool_input>; prints the exit code
  printf '{"session_id":"%s","transcript_path":"%s","cwd":"/repo","tool_name":"%s","tool_input":%s}' "$1" "$tmp/t" "$2" "$3" \
    | sh "$hook" 2>"$tmp/stderr"
  echo $?
}
expect() {  # expect <name> <want> <got>
  if [ "$2" = "$3" ]; then echo "OK   $1"; else echo "FAIL $1: want $2, got $3"; fail=1; fi
}
page() { printf '{"file_path":"%s","offset":%s,"limit":60,"line_numbers":true}' "$1" "$2"; }

expect "first paged read: allowed" 0 "$(run s1 Read "$(page "$tmp/small.py" 1)")"
expect "second paged read of a small file: blocked" 2 "$(run s1 Read "$(page "$tmp/small.py" 61)")"
grep -q '\[read-whole-file\]' "$tmp/stderr" && expect "message names the guardrail" 0 0 || expect "message names the guardrail" 0 1
grep -q '300 lines' "$tmp/stderr" && expect "message gives the line count" 0 0 || expect "message gives the line count" 0 1
expect "whole read after the block: allowed" 0 "$(run s1 Read "{\"file_path\":\"$tmp/small.py\",\"line_numbers\":true}")"
expect "third paged read of the same file: allowed (once per file)" 0 "$(run s1 Read "$(page "$tmp/small.py" 121)")"
expect "whole reads never block" 00 "$(run s2 Read "{\"file_path\":\"$tmp/small.py\"}")$(run s2 Read "{\"file_path\":\"$tmp/small.py\"}")"
expect "whole read, then paged read: allowed" 0 "$(run s2 Read "$(page "$tmp/small.py" 1)")"
expect "big file paged twice: allowed" 00 "$(run s3 Read "$(page "$tmp/big.py" 1)")$(run s3 Read "$(page "$tmp/big.py" 61)")"
expect "missing file paged twice: allowed" 00 "$(run s4 Read "$(page /nope.py 1)")$(run s4 Read "$(page /nope.py 61)")"
expect "other session, first paged read: allowed" 0 "$(run s5 Read "$(page "$tmp/small.py" 61)")"
expect "Grep with limit-like field: allowed" 0 "$(run s6 Grep '{"pattern":"a","path":"/repo","head_limit":10}')"
expect "test run: allowed" 0 "$(run s6 Execute '{"command":"pytest tests/test_a.py","timeout":60}')"

for f in small b c d; do run s7 Read "$(page "$tmp/$f.py" 1)" >/dev/null; done
n=0
for f in small b c d; do [ "$(run s7 Read "$(page "$tmp/$f.py" 61)")" = 2 ] && n=$((n + 1)); done
expect "four files paged twice: three blocked (session cap)" 3 "$n"

run s8 Read "$(page "$tmp/small.py" 1)" >/dev/null
printf '%s\n' '[read-whole-file] a' '[read-whole-file] b' '[read-whole-file] c' >> "$tmp/t"
expect "cap reached in transcript, new container: allowed" 0 "$(run s8 Read "$(page "$tmp/small.py" 61)")"
: > "$tmp/t"

run sp Read "$(page "$tmp/p.py" 1)" >/dev/null
for i in 1 2 3; do
  ( printf '{"session_id":"sp","transcript_path":"%s","tool_name":"Read","tool_input":%s}' "$tmp/t" "$(page "$tmp/p.py" $((i * 60)))" \
      | sh "$hook" 2>/dev/null; echo $? > "$tmp/par$i" ) &
done
wait
expect "3 parallel paged reads of one file: one blocked" 1 "$(cat "$tmp"/par1 "$tmp"/par2 "$tmp"/par3 | grep -c '^2$')"

expect "empty input: allowed" 0 "$(printf '' | sh "$hook" 2>/dev/null; echo $?)"
expect "garbage input: allowed" 0 "$(printf 'not json' | sh "$hook" 2>/dev/null; echo $?)"

rm -rf "$tmp"
exit $fail
