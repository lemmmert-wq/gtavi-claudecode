#!/usr/bin/env bash
# Start the private dashboard on each Codespaces attach/start.
# If installation failed earlier, retry in the background while the
# dashboard remains reachable and exposes the installation log.
set -u
cd "$(dirname "$0")/.."
mkdir -p .dashboard
if [ "$(cat .dashboard/install.status 2>/dev/null)" = "failed" ]; then
  echo "Vorige installatie mislukt; automatische herstelling starten."
  echo "retrying" > .dashboard/install.status
  nohup bash .devcontainer/setup.sh > .dashboard/retry.log 2>&1 < /dev/null &
fi
if command -v curl >/dev/null 2>&1 && curl --max-time 3 -fsS http://127.0.0.1:8765/api/status >/dev/null 2>&1; then
  echo "Mobiel dashboard actief op poort 8765"
  exit 0
fi
nohup python3 dashboard/app.py >> .dashboard/server.log 2>&1 < /dev/null &
echo "Mobiel dashboard wordt gestart op poort 8765 (PID $!)"
