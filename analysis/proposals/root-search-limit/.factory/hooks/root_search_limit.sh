#!/bin/sh
MARK='[root-search-limit]'

input=$(cat)
field() {
  printf '%s' "$input" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p" | head -n 1
}
[ "$(field tool_name)" = Grep ] || exit 0
[ "$(field output_mode)" = content ] || exit 0
printf '%s' "$input" | grep -q '"head_limit"' && exit 0

root="${FACTORY_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cwd=$(field cwd)
path=$(field path)
case "${path%/}" in
  ''|.|"${root%/}"|"${cwd%/}") ;;
  *) exit 0 ;;
esac

transcript=$(field transcript_path)
session=$(field session_id)
state="${TMPDIR:-/tmp}/root-search-limit-${session:-unknown}"
[ -e "$state" ] && exit 0
[ -f "$transcript" ] && grep -qF "$MARK" "$transcript" && exit 0

# Droid runs the hooks of a batch of parallel calls at once; mkdir lets only one of them block.
mkdir "$state" 2>/dev/null || exit 0
cat >&2 <<'MSG'
[root-search-limit] This search prints every matching line in the whole repository, which can be
thousands of lines that stay in context for the rest of the session. First find where the matches
are: run the same search with output_mode file_paths, or narrow path or glob_pattern to the
directories you need. Then search those files with output_mode content and a head_limit.
MSG
exit 2
