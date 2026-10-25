#!/bin/sh
MARK='[read-whole-file]'
MAX_LINES=600
MAX_BLOCKS=3

input=$(cat)
field() {
  printf '%s' "$input" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p" | head -n 1
}
[ "$(field tool_name)" = Read ] || exit 0
printf '%s' "$input" | grep -qE '"(offset|limit)"[[:space:]]*:' || exit 0
path=$(field file_path)
[ -n "$path" ] || exit 0

session=$(field session_id)
dir="${TMPDIR:-/tmp}/read-whole-file-${session:-unknown}"
mkdir -p "$dir" 2>/dev/null || exit 0
if ! grep -qxF "$path" "$dir/paged" 2>/dev/null; then
  printf '%s\n' "$path" >> "$dir/paged"
  exit 0
fi

[ -f "$path" ] || exit 0
lines=$(wc -l < "$path" 2>/dev/null | tr -d ' ')
[ -n "$lines" ] && [ "$lines" -le "$MAX_LINES" ] 2>/dev/null || exit 0

transcript=$(field transcript_path)
seen=0
[ -f "$transcript" ] && seen=$(grep -oF "$MARK" "$transcript" | wc -l | tr -d ' ')
blocks=$(ls -d "$dir"/b-* 2>/dev/null | wc -l | tr -d ' ')
[ "$seen" -lt "$MAX_BLOCKS" ] && [ "$blocks" -lt "$MAX_BLOCKS" ] || exit 0

# Droid runs the hooks of a batch of parallel calls at once; mkdir lets only one of them block.
key=$(printf '%s' "$path" | cksum | cut -d ' ' -f 1)
mkdir "$dir/b-$key" 2>/dev/null || exit 0
cat >&2 <<MSG
$MARK This session already read part of $path, and it has only $lines lines. Paging through it
in small ranges costs one turn per range. Read the whole file once: call Read again on this path
without offset and limit. Then work from that read, and do not page through this file again.
MSG
exit 2
