#!/bin/sh
MARK='[shell-fallback]'
KILLED='Command terminated by signal: SIGKILL'

input=$(cat)
field() {
  printf '%s' "$input" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p" | head -n 1
}
[ "$(field tool_name)" = Execute ] || exit 0
printf '%s' "$input" | grep -qE '"fireAndForget"[[:space:]]*:[[:space:]]*true' && exit 0
transcript=$(field transcript_path)
session=$(field session_id)
[ -f "$transcript" ] || exit 0

kills=$(grep -oF "$KILLED" "$transcript" | wc -l | tr -d ' ')
seen=$(grep -oF "$MARK" "$transcript" | wc -l | tr -d ' ')
[ "$kills" -gt "$seen" ] 2>/dev/null || exit 0

# Droid runs the hooks of a batch of parallel calls at once; mkdir lets only one of them block.
mkdir "${TMPDIR:-/tmp}/shell-fallback-${session:-unknown}-$kills" 2>/dev/null || exit 0
cat >&2 <<'MSG'
[shell-fallback] A shell command in this session was killed (SIGKILL). Here such kills tend to
repeat for every foreground command, even trivial ones, so do not spend calls probing the shell.
Run this command again with fireAndForget set to true. Redirect its output to a log file under
/tmp and append the exit code, for example: <command> > /tmp/run.log 2>&1; echo EXIT=$? >> /tmp/run.log
Then read the log file. If it has no EXIT line yet, the command is still running: read it again.
MSG
exit 2
