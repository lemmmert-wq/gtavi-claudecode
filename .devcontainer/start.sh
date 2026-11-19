#!/usr/bin/env bash
# Ensure the private dashboard is running whenever a Codespace starts/attaches.
set -u
cd "$(dirname "$0")/.."
mkdir -p .dashboard
if command -v curl >/dev/null 2>&1 && curl --max-time 3 -fsS http://127.0.0.1:8765/api/status >/dev/null 2>&1; then
  echo "Mobiel dashboard actief op poort 8765"
  exit 0
fi
nohup python3 dashboard/app.py >> .dashboard/server.log 2>&1 < /dev/null &
echo "Mobiel dashboard wordt gestart op poort 8765 (PID $!)"
