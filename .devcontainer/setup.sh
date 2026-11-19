#!/usr/bin/env bash
# Automatic, idempotent setup for GitHub Codespaces.
# Logs and progress remain visible in the mobile web dashboard.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
mkdir -p .dashboard
echo "running" > .dashboard/install.status
exec >> .dashboard/install.log 2>&1
echo ""
echo "=== Installatie gestart: $(date -u '+%Y-%m-%d %H:%M UTC') ==="
trap 'code=$?; echo "Installatiefout (code $code) op regel $LINENO"; echo "failed" > .dashboard/install.status; exit 0' ERR
echo "Python: $(python3 --version)"
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "FFmpeg installeren..."
  # A Codespaces image can contain a third-party Yarn APT feed whose
  # signing key is expired. Do NOT bypass APT signature verification:
  # disable only that optional feed and retry with signed Debian sources.
  if ! sudo apt-get update; then
    echo "APT-update mislukt. Eventuele defecte Yarn-pakketbron uitschakelen."
    for source in /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
      [ -f "$source" ] || continue
      if grep -Fq "dl.yarnpkg.com" "$source"; then
        echo "Defecte externe Yarn-bron uitschakelen: $source"
        sudo mv "$source" "$source.disabled"
      fi
    done
    sudo apt-get update
  fi
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ffmpeg
else
  echo "FFmpeg is al aanwezig."
fi
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check --upgrade pip
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
.venv/bin/python -c 'import yt_dlp, faster_whisper, numpy; print("Python-pakketten OK")'
ffmpeg -version | head -n 1
echo "ready" > .dashboard/install.status
echo "=== Installatie geslaagd ==="
