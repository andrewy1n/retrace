#!/bin/sh
MARK='[read-whole-file]'
SMALL_WINDOW=200
WIDE_WINDOW=400
MAX_BLOCKS=3

input=$(cat)
field() {
  printf '%s' "$input" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p" | head -n 1
}
number() {
  printf '%s' "$input" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\\([0-9][0-9]*\\).*/\\1/p" | head -n 1
}
[ "$(field tool_name)" = Read ] || exit 0
path=$(field file_path)
[ -n "$path" ] || exit 0

session=$(field session_id)
dir="${TMPDIR:-/tmp}/read-whole-file-${session:-unknown}"
mkdir -p "$dir" 2>/dev/null || exit 0
if ! grep -qxF "$path" "$dir/read" 2>/dev/null; then
  printf '%s\n' "$path" >> "$dir/read"
  exit 0
fi

limit=$(number limit)
[ -n "$limit" ] && [ "$limit" -lt "$SMALL_WINDOW" ] 2>/dev/null || exit 0

transcript=$(field transcript_path)
seen=0
[ -f "$transcript" ] && seen=$(grep -oF "$MARK" "$transcript" | wc -l | tr -d ' ')
blocks=$(ls -d "$dir"/b-* 2>/dev/null | wc -l | tr -d ' ')
[ "$seen" -lt "$MAX_BLOCKS" ] && [ "$blocks" -lt "$MAX_BLOCKS" ] || exit 0

# Droid runs the hooks of a batch of parallel calls at once; mkdir lets only one of them block.
key=$(printf '%s' "$path" | cksum | cut -d ' ' -f 1)
mkdir "$dir/b-$key" 2>/dev/null || exit 0
cat >&2 <<MSG
$MARK This session already read $path.
This call reads it again in a window of only $limit lines, and each small window costs one more
turn. If you do not know where the code you need is, run Grep with line numbers on this file
first. Then read one window of about $WIDE_WINDOW lines (offset and limit) that covers every range
you need, and work from that read.
MSG
exit 2
