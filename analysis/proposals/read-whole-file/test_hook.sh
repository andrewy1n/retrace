#!/bin/sh
# Run from the repo root: sh analysis/proposals/read-whole-file/test_hook.sh

here=$(cd "$(dirname "$0")" && pwd)
hook="$here/.factory/hooks/read_whole_file.sh"
tmp=$(mktemp -d)
export TMPDIR="$tmp"
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
page() { printf '{"file_path":"%s","offset":%s,"limit":%s,"line_numbers":true}' "$1" "$2" "${3:-60}"; }
whole() { printf '{"file_path":"%s","line_numbers":true}' "$1"; }

expect "first paged read: allowed" 0 "$(run s1 Read "$(page /repo/a.py 1)")"
expect "second small window: blocked" 2 "$(run s1 Read "$(page /repo/a.py 61)")"
grep -q '\[read-whole-file\]' "$tmp/stderr" && expect "message names the guardrail" 0 0 || expect "message names the guardrail" 0 1
grep -q 'window of only 60 lines' "$tmp/stderr" && expect "message gives the window" 0 0 || expect "message gives the window" 0 1
expect "wide window after the block: allowed" 0 "$(run s1 Read "$(page /repo/a.py 1 400)")"
expect "small window again, same file: allowed (once per file)" 0 "$(run s1 Read "$(page /repo/a.py 500)")"
expect "whole read, then small window: blocked" 02 "$(run s2 Read "$(whole /repo/b.py)")$(run s2 Read "$(page /repo/b.py 210 25)")"
expect "whole reads never block" 00 "$(run s3 Read "$(whole /repo/c.py)")$(run s3 Read "$(whole /repo/c.py)")"
expect "reread with a window of 200: allowed" 00 "$(run s4 Read "$(page /repo/d.py 1)")$(run s4 Read "$(page /repo/d.py 61 200)")"
expect "reread with offset only: allowed" 00 "$(run s5 Read "$(page /repo/e.py 1)")$(run s5 Read '{"file_path":"/repo/e.py","offset":300}')"
expect "small windows of two different files: allowed" 00 "$(run s6 Read "$(page /repo/f.py 1)")$(run s6 Read "$(page /repo/g.py 1)")"
expect "other session, first small window: allowed" 0 "$(run s7 Read "$(page /repo/a.py 61)")"
expect "Grep: allowed" 0 "$(run s8 Grep '{"pattern":"a","path":"/repo/a.py","head_limit":10}')"
expect "test run: allowed" 0 "$(run s8 Execute '{"command":"pytest tests/test_a.py","timeout":60}')"

for f in h i j k; do run s9 Read "$(page /repo/$f.py 1)" >/dev/null; done
n=0
for f in h i j k; do [ "$(run s9 Read "$(page /repo/$f.py 61)")" = 2 ] && n=$((n + 1)); done
expect "four files reread in small windows: three blocked (session cap)" 3 "$n"

run s10 Read "$(page /repo/a.py 1)" >/dev/null
printf '%s\n' '[read-whole-file] a' '[read-whole-file] b' '[read-whole-file] c' >> "$tmp/t"
expect "cap reached in transcript, new container: allowed" 0 "$(run s10 Read "$(page /repo/a.py 61)")"
: > "$tmp/t"

run sp Read "$(page /repo/p.py 1)" >/dev/null
for i in 1 2 3; do
  ( printf '{"session_id":"sp","transcript_path":"%s","tool_name":"Read","tool_input":%s}' "$tmp/t" "$(page /repo/p.py $((i * 60)))" \
      | sh "$hook" 2>/dev/null; echo $? > "$tmp/par$i" ) &
done
wait
expect "3 parallel small windows of one file: one blocked" 1 "$(cat "$tmp"/par1 "$tmp"/par2 "$tmp"/par3 | grep -c '^2$')"

expect "empty input: allowed" 0 "$(printf '' | sh "$hook" 2>/dev/null; echo $?)"
expect "garbage input: allowed" 0 "$(printf 'not json' | sh "$hook" 2>/dev/null; echo $?)"

rm -rf "$tmp"
exit $fail
