#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
if ! docker compose version >/dev/null 2>&1; then
  echo "Install Docker Engine with Compose v2+, or Docker Desktop." >&2
  exit 1
fi
if [ ! -f .env.docker ]; then
  # Generate once; retain this file so sessions and encrypted tokens survive restarts.
  secret=$(docker run --rm python:3.11-slim python -c 'import secrets; print(secrets.token_urlsafe(48))')
  (umask 077; printf 'SESSION_SECRET=%s\nHOST_PORT=7331\n' "$secret" > .env.docker)
fi
docker compose --env-file .env.docker up -d --build --wait --wait-timeout 180
address=$(docker compose --env-file .env.docker port app 7331)
printf '\nAI Tasker is ready: http://%s\n' "$address"
