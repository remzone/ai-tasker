#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .runtime
if [[ -x .tools/pg/usr/lib/postgresql/18/bin/pg_ctl ]]; then
  export LD_LIBRARY_PATH="$PWD/.tools/pg/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  if ! .tools/pg/usr/lib/postgresql/18/bin/pg_ctl -D "$PWD/.runtime/pgdata" status >/dev/null 2>&1; then
    .tools/pg/usr/lib/postgresql/18/bin/pg_ctl -D "$PWD/.runtime/pgdata" -l "$PWD/.runtime/postgres.log" -o "-p 5436 -h 127.0.0.1 -k $PWD/.runtime" start
  fi
fi
if [[ -f .runtime/app.pid ]] && kill -0 "$(cat .runtime/app.pid)" 2>/dev/null && [[ "$(readlink -f "/proc/$(cat .runtime/app.pid)/cwd")" == "$PWD" ]] && tr "\0" " " < "/proc/$(cat .runtime/app.pid)/cmdline" | rg -q "kanban serve"; then
  echo 'AI Tasker уже запущен: http://localhost:7331'
  exit 0
fi
.venv/bin/kanban migrate
nohup .venv/bin/kanban serve --host 127.0.0.1 --port 7331 > .runtime/app.log 2>&1 &
echo "$!" > .runtime/app.pid
for attempt in {1..30}; do
  if curl -fsS http://127.0.0.1:7331/api/setup-status >/dev/null 2>&1; then
    echo 'AI Tasker: http://localhost:7331'
    exit 0
  fi
  sleep 1
done
echo 'Не удалось запустить AI Tasker. См. .runtime/app.log' >&2
exit 1
