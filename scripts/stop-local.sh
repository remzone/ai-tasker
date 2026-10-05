#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .runtime/app.pid ]]; then
  pid="$(cat .runtime/app.pid)"
  if kill -0 "$pid" 2>/dev/null; then
    # Never signal a reused PID belonging to an unrelated process.
    if [[ "$(readlink -f "/proc/$pid/cwd")" == "$PWD" ]] && tr '\0' ' ' < "/proc/$pid/cmdline" | rg -q 'kanban serve'; then
      kill "$pid"
    fi
  fi
  rm -f .runtime/app.pid
fi
if [[ -x .tools/pg/usr/lib/postgresql/18/bin/pg_ctl ]]; then
  export LD_LIBRARY_PATH="$PWD/.tools/pg/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  if .tools/pg/usr/lib/postgresql/18/bin/pg_ctl -D "$PWD/.runtime/pgdata" status >/dev/null 2>&1; then
    .tools/pg/usr/lib/postgresql/18/bin/pg_ctl -D "$PWD/.runtime/pgdata" stop -m fast
  fi
fi
