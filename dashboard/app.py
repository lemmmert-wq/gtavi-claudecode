#!/usr/bin/env python3
"""Private Codespaces web dashboard for the existing GTA VI clipping scripts.

No automatic downloading, video publishing, or background scanning. Actions are
only started by an authenticated Codespaces browser session, one at a time.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".dashboard"
DATA.mkdir(exist_ok=True)
PY = ROOT / ".venv" / "bin" / "python"
PORT = int(os.environ.get("CLIP_DASHBOARD_PORT", "8765"))
LOCK = threading.Lock()
STATE = {"busy": False, "task": "", "message": "Klaar om te starten", "updated": "", "failed": False}

def status():
    try:
        install = (DATA / "install.status").read_text().strip()
    except FileNotFoundError:
        install = "niet gestart"
    try:
        logtail = (DATA / "install.log").read_text(errors="replace")[-2200:]
    except FileNotFoundError:
        logtail = ""
    packages = {}
    for label, name in (("yt-dlp", "yt_dlp"), ("Whisper", "faster_whisper"), ("NumPy", "numpy")):
        if PY.exists():
            r = subprocess.run([str(PY), "-c", "import " + name], capture_output=True, timeout=12)
            packages[label] = r.returncode == 0
        else:
            packages[label] = False
    with LOCK:
        active = dict(STATE)
    return {"install": install, "ffmpeg": bool(shutil.which("ffmpeg")),
            "python": PY.exists(), "packages": packages, "install_log": logtail, **active}

def valid_url(url):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return (parsed.scheme == "https" and
                host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.twitch.tv", "twitch.tv"} and
                bool(parsed.path) and len(url) <= 400)
    except ValueError:
        return False

def run_task(action, payload):
    try:
        commands = {
            "trends": [str(PY), "scripts/trends.py", "--query", "gta 6", "--hours", "24",
                       "--limit", "12", "--out", str(DATA / "trends.md")],
            "streams": [str(PY), "scripts/streams.py", "--query", "gta 6", "--limit", "10",
                        "--out", str(DATA / "streams.md")],
        }
        if action in commands:
            cmd = commands[action]
            timeout = 600
        elif action == "analyze":
            url = str(payload["url"]).strip()
            cmd = [str(PY), "scripts/moments.py", url, "--top", "5", "--max-minutes", "15"]
            timeout = 2400
        elif action == "clip":
            job = str(payload["job"])
            pick = int(payload["pick"])
            if not re.fullmatch(r"[a-z0-9-]{3,70}", job) or not 1 <= pick <= 20:
                raise ValueError("Ongeldige clipselectie")
            src = ROOT / "jobs" / job / "candidates.json"
            if not src.is_file():
                raise ValueError("Analyse niet gevonden")
            options = json.loads(src.read_text())
            if not any(int(c["n"]) == pick for c in options["candidates"]):
                raise ValueError("Dat moment bestaat niet")
            hook = str(payload.get("hook", "")).strip()[:90]
            cmd = [str(PY), "scripts/cut.py", str(src.parent), "--pick", str(pick),
                   "--layout", "blur", "--hook", hook]
            timeout = 1200
        else:
            raise ValueError("Onbekende opdracht")
        if not PY.is_file():
            raise RuntimeError("Python-omgeving is nog niet geïnstalleerd; bekijk de installatiestatus")
        done = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, errors="replace", timeout=timeout, check=False)
        message = done.stdout[-6500:] or "Geen uitvoer"
        if done.returncode:
            raise RuntimeError("Opdracht mislukt:\n" + message)
        failure = False
    except subprocess.TimeoutExpired:
        message, failure = "De maximale verwerkingstijd is bereikt. Probeer een kortere video.", True
    except Exception as exc:
        message, failure = str(exc), True
    with LOCK:
        STATE.update(busy=False, failed=failure, message=message, updated=time.strftime("%H:%M:%S"))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def reply(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            data = (ROOT / "dashboard" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; media-src 'self'")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/status":
            self.reply(status())
        elif path == "/api/results":
            kind = parse_qs(urlparse(self.path).query).get("kind", [""])[0]
            if kind not in ("trends", "streams"):
                return self.reply({"error": "Onbekende resultaten"}, 400)
            p = DATA / (kind + ".md")
            self.reply({"text": p.read_text(errors="replace")[-42000:] if p.exists() else ""})
        elif path == "/api/jobs":
            jobs = []
            for p in sorted((ROOT / "jobs").glob("*/candidates.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
                try:
                    d = json.loads(p.read_text())
                    edits = p.parent / "edits"
                    jobs.append({"id": p.parent.name, "title": d.get("info", {}).get("title", p.parent.name),
                                 "source": d.get("info", {}).get("webpage_url", ""),
                                 "candidates": d.get("candidates", []),
                                 "clips": [int(f.stem.split("_")[-1]) for f in edits.glob("clip_*.mp4")] if edits.exists() else []})
                except (ValueError, OSError, KeyError):
                    continue
            self.reply({"jobs": jobs})
        elif path.startswith("/video/"):
            m = re.fullmatch(r"/video/([a-z0-9-]{3,70})/clip_([0-9]{1,2})\.mp4", path)
            if not m:
                return self.send_error(404)
            p = ROOT / "jobs" / m[1] / "edits" / ("clip_" + str(int(m[2])) + ".mp4")
            if not p.is_file():
                return self.send_error(404)
            self.stream_video(p)
        else:
            self.send_error(404)

    def stream_video(self, p):
        size = p.stat().st_size
        start, end = 0, size - 1
        header = self.headers.get("Range", "")
        partial = False
        if header:
            m = re.fullmatch(r"bytes=(\d+)-(\d*)", header)
            if not m:
                return self.send_error(416)
            start = int(m[1])
            if m[2]:
                end = min(end, int(m[2]))
            if start >= size or start > end:
                return self.send_error(416)
            partial = True
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", 'inline; filename="' + p.name + '"')
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with p.open("rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(1024 * 512, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)

    def do_POST(self):
        if urlparse(self.path).path != "/api/run":
            return self.reply({"error": "Niet gevonden"}, 404)
        # Browser-origin check: do not allow another site to trigger downloads.
        origin = self.headers.get("Origin", "")
        host = self.headers.get("Host", "")
        if not origin or urlparse(origin).netloc != host:
            return self.reply({"error": "Ongeldige aanvraagherkomst"}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 3000:
                return self.reply({"error": "Ongeldige gegevens"}, 400)
            payload = json.loads(self.rfile.read(length))
            action = payload.get("action")
            if action not in ("trends", "streams", "analyze", "clip"):
                return self.reply({"error": "Onbekende actie"}, 400)
            if action == "analyze" and (not payload.get("permission") or not valid_url(str(payload.get("url", "")))):
                return self.reply({"error": "Gebruik een geldige YouTube/Twitch-URL en bevestig toestemming"}, 400)
            with LOCK:
                if STATE["busy"]:
                    return self.reply({"error": "Er wordt al een opdracht uitgevoerd"}, 409)
                STATE.update(busy=True, task=action, message="Gestart …", failed=False, updated=time.strftime("%H:%M:%S"))
            threading.Thread(target=run_task, args=(action, payload), daemon=True).start()
            self.reply({"started": action}, 202)
        except (ValueError, TypeError, KeyError) as exc:
            self.reply({"error": "Fout in aanvraag: " + str(exc)}, 400)

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"GTA Clipper Dashboard luistert op poort {PORT}", flush=True)
    server.serve_forever()
