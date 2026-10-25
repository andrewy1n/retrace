#!/bin/sh
# PreToolUse guardrail: after LIMIT tool calls with no file edit, block one call and ask
# for the first edit. It fires at most once per session.
#
# The count comes from the session transcript (transcript_path in the hook input), so a
# resumed or forked session counts the calls it already made. A batch of parallel calls
# gets one block, not one per call (checked on Droid 0.249.0). POSIX sh, grep and sed only,
# so it runs in any image. Any failure exits 0 and lets the call through.

LIMIT=10
MARK='[explore-budget]'
EDIT_TOOLS='Edit|Create|MultiEdit|ApplyPatch'

input=$(cat)
field() {
  printf '%s' "$input" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p" | head -n 1
}
tool=$(field tool_name)
transcript=$(field transcript_path)
session=$(field session_id)

case "$tool" in
  ''|Edit|Create|MultiEdit|ApplyPatch) exit 0 ;;
esac
[ -f "$transcript" ] || exit 0

state="${TMPDIR:-/tmp}/explore-budget-${session:-unknown}"
[ -e "$state" ] && exit 0
grep -qF "$MARK" "$transcript" && exit 0

# Tool calls in order. Stop at the first edit: after it the guardrail is done.
names=$(grep -o '"type":"tool_use","id":"[^"]*","name":"[^"]*"' "$transcript" | sed 's/.*"name":"//; s/"$//')
n=0
for t in $names; do
  if printf '%s' "$t" | grep -qxE "$EDIT_TOOLS"; then
    exit 0
  fi
  n=$((n + 1))
done
[ "$n" -ge "$LIMIT" ] || exit 0

# Droid runs one hook per call in a batch of parallel calls, all at once. mkdir is atomic,
# so only the first of them claims the nudge and the rest let their call through.
mkdir "$state" 2>/dev/null || exit 0
cat >&2 <<EOF
$MARK This session has made $n read, search, and shell calls without editing a file.
Stop exploring for now. State in one sentence the change you will make and where, then make
that first edit. When you need more of a file, read one larger range instead of paging through
it in small chunks. Read again only to answer one specific question the edit depends on.
EOF
exit 2
