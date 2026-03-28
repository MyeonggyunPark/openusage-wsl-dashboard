#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_URL="http://127.0.0.1:6736/api/v1/usage"
FRONTEND_URL="http://127.0.0.1:5173/"
BACKEND_LOG="/tmp/openusage-backend.log"
FRONTEND_LOG="/tmp/openusage-frontend.log"
OPEN_STAMP="/tmp/openusage-dashboard.last-open"
OPEN_COOLDOWN_SECONDS=15

probe_url() {
  curl -fsS --max-time 2 "$1" >/dev/null 2>&1
}

start_backend() {
  (
    cd "$ROOT_DIR"
    nohup "$ROOT_DIR/.venv/bin/python" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 6736 >"$BACKEND_LOG" 2>&1 &
  )
}

start_frontend() {
  (
    cd "$ROOT_DIR/frontend"
    nohup pnpm dev --host 127.0.0.1 --port 5173 >"$FRONTEND_LOG" 2>&1 &
  )
}

wait_for_url() {
  local url="$1"
  local attempts="${2:-40}"
  local delay="${3:-0.5}"
  local i

  for ((i = 0; i < attempts; i += 1)); do
    if probe_url "$url"; then
      return 0
    fi
    sleep "$delay"
  done

  return 1
}

open_dashboard() {
  local now
  local last_open=0

  if [[ "${OPENUSAGE_SKIP_OPEN:-0}" == "1" ]]; then
    return 0
  fi

  now="$(date +%s)"
  if [[ -f "$OPEN_STAMP" ]]; then
    read -r last_open <"$OPEN_STAMP" || true
  fi

  if (( now - last_open < OPEN_COOLDOWN_SECONDS )); then
    return 0
  fi

  printf '%s\n' "$now" >"$OPEN_STAMP"

  if command -v wslview >/dev/null 2>&1; then
    nohup wslview "$FRONTEND_URL" >/dev/null 2>&1 &
    return 0
  fi

  if command -v cmd.exe >/dev/null 2>&1; then
    nohup cmd.exe /C start "" "$FRONTEND_URL" >/dev/null 2>&1 &
    return 0
  fi

  if command -v powershell.exe >/dev/null 2>&1; then
    nohup powershell.exe -NoProfile -Command "Start-Process '$FRONTEND_URL'" >/dev/null 2>&1 &
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    nohup xdg-open "$FRONTEND_URL" >/dev/null 2>&1 &
  fi
}

main() {
  if ! probe_url "$BACKEND_URL"; then
    start_backend
  fi

  if ! probe_url "$FRONTEND_URL"; then
    start_frontend
  fi

  wait_for_url "$BACKEND_URL"
  wait_for_url "$FRONTEND_URL"
  open_dashboard
}

main "$@"
