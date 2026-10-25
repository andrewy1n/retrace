#!/usr/bin/env bash
# Usage: dashboard/run.sh sources | dev | live | build | preview
# live is dev plus a `sources` run every REFRESH seconds (default 30). Reload the browser to see new data.
# PROPOSALS and JOBS override the proposal and job directories that proposal_list.py scans.
# Reads TIGER_DASHBOARD_URL (read-only role) from the repo .env and passes it to Evidence as environment variables.
set -euo pipefail
cd "$(dirname "$0")"
refresh() {
  python3 -I proposal_list.py ${PROPOSALS:+--proposals "$PROPOSALS"} ${JOBS:+--jobs "$JOBS"}
  python3 -I fork_view.py
  rm -rf .evidence/template/static/data/proposal_list .evidence/template/static/data/fork_view
  npx evidence sources
}
set -a; . ../.env; set +a
eval "$(python3 -I - <<'PY'
import os, shlex
from urllib.parse import urlparse, unquote
u = urlparse(os.environ["TIGER_DASHBOARD_URL"])
for k, v in {"host": u.hostname, "port": u.port, "database": u.path.lstrip("/"),
             "user": unquote(u.username), "password": unquote(u.password), "ssl": "true"}.items():
    print(f"export EVIDENCE_SOURCE__tiger__{k}={shlex.quote(str(v))}")
PY
)"
unset TIGER_DASHBOARD_URL TIGER_DATABASE_URL TIGER_ANALYSIS_URL FACTORY_API_KEY VULTR_API_KEY
case "${1:-}" in
  sources) refresh ;;
  dev) exec npx evidence dev --port "${PORT:-3100}" ;;
  live)
    ( while sleep "${REFRESH:-30}"; do refresh > /dev/null 2>&1 || true; done ) &
    trap 'kill $!' EXIT
    npx evidence dev --port "${PORT:-3100}" ;;
  build) exec npx evidence build ;;
  preview) exec npx evidence preview --port "${PORT:-3100}" ;;
  *) sed -n '2,4p' "$0"; exit 1 ;;
esac
