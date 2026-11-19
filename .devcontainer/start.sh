#!/usr/bin/env bash
# Private Codespaces dashboard bootstrap.
# On new editor attachment, safely fast-forward a clean checkout from the
# owner's fork (main). No reset, force-pull, or overwrite of local changes.
set -u
cd "$(dirname "$0")/.."
mkdir -p .dashboard
exec 9>.dashboard/start.lock
if command -v flock >/dev/null 2>&1; then
  flock -n 9 || exit 0
fi

changed=0
if command -v git >/dev/null 2>&1 &&
   [ "$(git branch --show-current 2>/dev/null)" = "main" ] &&
   [ -z "$(git status --porcelain --untracked-files=no 2>/dev/null)" ]; then
  before="$(git rev-parse HEAD 2>/dev/null)"
  if git pull --ff-only origin main >> .dashboard/update.log 2>&1; then
    after="$(git rev-parse HEAD 2>/dev/null)"
    if [ "$after" != "$before" ]; then
      changed=1
      echo "GitHub-bijwerking automatisch ontvangen: $after" >> .dashboard/update.log
    fi
  else
    echo "Automatisch bijwerken is niet gelukt; lokale bestanden zijn niet overschreven." >> .dashboard/update.log
  fi
fi

if [ "$(cat .dashboard/install.status 2>/dev/null)" = "failed" ]; then
  echo "Vorige installatie mislukt; automatische herstelling starten."
  echo "retrying" > .dashboard/install.status
  nohup bash .devcontainer/setup.sh > .dashboard/retry.log 2>&1 < /dev/null &
fi

running=0
if command -v curl >/dev/null 2>&1 &&
   curl --max-time 3 -fsS http://127.0.0.1:8765/api/status >/dev/null 2>&1; then
  running=1
fi

# A user may have synchronized GitHub before attaching. In that case
# 'changed' is zero, but the running Python process still serves old code.
if [ "$running" -eq 1 ]; then
  code_now="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  code_live="$(python3 - <<'PY'
import json
import urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:8765/api/version", timeout=3) as res:
        print(json.load(res).get("revision") or "unknown")
except Exception:
    print("unknown")
PY
)"
  if [ "$code_now" != "$code_live" ]; then
    changed=1
  fi
fi

if [ "$changed" -eq 1 ] && [ "$running" -eq 1 ]; then
  # Never restart while a clip/live task is running.
  busy="$(python3 - <<'PY'
import json
import urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=3) as res:
        print("yes" if json.load(res).get("busy") else "no")
except Exception:
    print("unknown")
PY
)"
  if [ "$busy" = "no" ] && command -v pgrep >/dev/null 2>&1; then
    # Only terminate the known Python dashboard process, not other services.
    for pid in $(pgrep -f -x 'python3 dashboard/app.py' 2>/dev/null || true); do
      kill "$pid" 2>/dev/null || true
    done
    sleep 1
    running=0
  else
    echo "Dashboard is bezig of serverproces onbekend; bij de volgende herstart worden de wijzigingen geladen." >> .dashboard/update.log
  fi
fi

if [ "$running" -eq 1 ]; then
  echo "Mobiel dashboard actief op poort 8765"
  exit 0
fi
if command -v curl >/dev/null 2>&1 &&
   curl --max-time 3 -fsS http://127.0.0.1:8765/api/status >/dev/null 2>&1; then
  echo "Bestaande webserver is nog actief; geen tweede server gestart."
  exit 0
fi

nohup python3 dashboard/app.py >> .dashboard/server.log 2>&1 < /dev/null &
echo "Mobiel dashboard wordt gestart op poort 8765 (PID $!)"
