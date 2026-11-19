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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dashboard.workflow import add_campaign, add_post, list_campaigns, list_posts, get_campaign, campaign_rules_file

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
    packages = {"yt-dlp": False, "Whisper": False, "NumPy": False}
    if PY.is_file():
        try:
            check = ("import importlib.util,json; print(json.dumps({"
                     "'yt-dlp':importlib.util.find_spec('yt_dlp') is not None,"
                     "'Whisper':importlib.util.find_spec('faster_whisper') is not None,"
                     "'NumPy':importlib.util.find_spec('numpy') is not None}))")
            probe = subprocess.run([str(PY), "-c", check], text=True, capture_output=True, timeout=6)
            if probe.returncode == 0:
                packages = json.loads(probe.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
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
        elif action in ("clip", "translate", "check"):
            job = str(payload.get("job", ""))
            pick = int(payload.get("pick") or 0)
            if not re.fullmatch(r"[a-z0-9-]{3,70}", job) or not 1 <= pick <= 20:
                raise ValueError("Ongeldige clipselectie")
            src = ROOT / "jobs" / job / "candidates.json"
            if not src.is_file():
                raise ValueError("Analyse niet gevonden")
            options = json.loads(src.read_text())
            if not any(int(c["n"]) == pick for c in options["candidates"]):
                raise ValueError("Dat moment bestaat niet")
            clip = src.parent / "edits" / f"clip_{pick}.mp4"
            if action == "clip":
                hook = str(payload.get("hook", "")).strip()[:90]
                layout = str(payload.get("layout", "blur"))
                captions = str(payload.get("captions", "word"))
                if layout not in ("blur", "fill", "facecam", "react") or captions not in ("word", "bubble", "none"):
                    raise ValueError("Onbekend formaat of ondertitelstijl")
                cmd = [str(PY), "scripts/cut.py", str(src.parent), "--pick", str(pick),
                       "--layout", layout, "--captions", captions, "--hook", hook]
                timeout = 1800
            elif action == "translate":
                if not clip.is_file():
                    raise ValueError("Maak eerst de hoofdclip")
                langs = str(payload.get("langs", ""))
                chosen = [v.strip() for v in langs.split(",") if v.strip()]
                if not chosen or len(chosen) > 4 or any(v not in ("es", "pt", "de", "ru") for v in chosen):
                    raise ValueError("Kies maximaal vier ondersteunde talen")
                # Original translate.py supports blur/fill/facecam but not react.
                meta_path = clip.with_suffix(".json")
                layout = "blur"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text())
                    layout = meta.get("layout", "blur")
                    if layout == "react":
                        raise ValueError("React-formaat kan nog niet vertaald worden")
                cmd = [str(PY), "scripts/translate.py", str(src.parent), "--pick", str(pick),
                       "--langs", ",".join(chosen)]
                timeout = 1800
            else:
                if not clip.is_file():
                    raise ValueError("Maak eerst de clip")
                campaign_id = str(payload.get("campaign_id", ""))
                campaign = get_campaign(DATA, campaign_id) if campaign_id else None
                if campaign_id and not campaign:
                    raise ValueError("Campagne niet gevonden")
                if campaign and not campaign.get("rules_reviewed"):
                    raise ValueError("Controleer eerst de campagneregels en sla deze als nagelezen op")
                caption = str(payload.get("caption", "")).strip()[:1000]
                cmd = [str(PY), "scripts/check.py", str(clip), "--caption", caption]
                rules_path = campaign_rules_file(DATA, campaign)
                if rules_path:
                    cmd += ["--campaign", str(rules_path)]
                timeout = 60
        elif action == "live":
            url = str(payload.get("url", "")).strip()
            if not payload.get("permission") or not valid_url(url):
                raise ValueError("Geldige livestream-URL en toestemming zijn vereist")
            minutes = int(payload.get("minutes") or 5)
            if not 1 <= minutes <= 15:
                raise ValueError("Kies 1 tot 15 minuten")
            cmd = [str(PY), "scripts/live.py", url, "--minutes", str(minutes)]
            timeout = (minutes + 3) * 60
        else:
            raise ValueError("Onbekende opdracht")
        if not PY.is_file():
            raise RuntimeError("Python-omgeving is nog niet geïnstalleerd; bekijk de installatiestatus")
        done = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, errors="replace", timeout=timeout, check=False)
        message = done.stdout[-6500:] or "Geen uitvoer"
        if done.returncode:
            raise RuntimeError("Opdracht mislukt:\n" + message)
        if action == "check":
            message = ("Technische controle van formaat en ingevulde tekst. Geen bevestiging van beeldrechten, "
                       "campagnegoedkeuring of uitbetaling.\n" + message)
        if action == "live":
            message = ("Livefragmenten zijn ruwe opnames, niet automatisch verticale clips.\n" + message)
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
            response = {"text": p.read_text(errors="replace")[-42000:] if p.exists() else ""}
            if kind == "trends":
                sidecar = DATA / "trends.json"
                try:
                    summary = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
                    response["items"] = summary.get("items", [])
                    response["meta"] = summary.get("meta", {})
                except (ValueError, OSError):
                    response["items"] = []
            self.reply(response)
        elif path == "/api/jobs":
            jobs = []
            for p in sorted((ROOT / "jobs").glob("*/candidates.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
                try:
                    d = json.loads(p.read_text())
                    edits = p.parent / "edits"
                    files = list(edits.glob("clip_*.mp4")) if edits.exists() else []
                    base = []
                    translated = {}
                    for f in files:
                        m = re.fullmatch(r"clip_(\d+)(?:_(es|pt|de|ru))?", f.stem)
                        if not m:
                            continue
                        n = int(m[1])
                        if m[2]:
                            translated.setdefault(str(n), []).append(m[2])
                        else:
                            base.append(n)
                    jobs.append({"id": p.parent.name, "title": d.get("info", {}).get("title", p.parent.name),
                                 "source": d.get("info", {}).get("webpage_url", ""),
                                 "candidates": d.get("candidates", []),
                                 "clips": sorted(base), "translations": translated})
                except (ValueError, OSError, KeyError):
                    continue
            self.reply({"jobs": jobs})
        elif path.startswith("/video/"):
            m = re.fullmatch(r"/video/([a-z0-9-]{3,70})/clip_([0-9]{1,2})(?:_(es|pt|de|ru))?\.mp4", path)
            if not m:
                return self.send_error(404)
            suffix = ("_" + m[3]) if m[3] else ""
            p = ROOT / "jobs" / m[1] / "edits" / ("clip_" + str(int(m[2])) + suffix + ".mp4")
            if not p.is_file():
                return self.send_error(404)
            self.stream_video(p)
        elif path == "/api/campaigns":
            self.reply({"campaigns": list_campaigns(DATA)})
        elif path == "/api/posts":
            self.reply({"posts": list_posts(DATA)})
        elif path == "/api/liveclips":
            results = []
            for f in sorted((ROOT / "jobs").glob("*/live/spike_*.mp4"),
                            key=lambda item: item.stat().st_mtime, reverse=True)[:25]:
                m = re.fullmatch(r"spike_([0-9]{1,3})", f.stem)
                if m and re.fullmatch(r"[a-z0-9-]{3,70}", f.parent.parent.name):
                    results.append({"url": "/live/" + f.parent.parent.name + "/" + f.name,
                                    "job": f.parent.parent.name, "clip": int(m[1]),
                                    "size_bytes": f.stat().st_size})
            self.reply({"clips": results})
        elif path.startswith("/live/"):
            m = re.fullmatch(r"/live/([a-z0-9-]{3,70})/spike_([0-9]{1,3})\.mp4", path)
            if not m:
                return self.send_error(404)
            p = ROOT / "jobs" / m[1] / "live" / ("spike_" + str(int(m[2])) + ".mp4")
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
        path = urlparse(self.path).path
        if path not in ("/api/run", "/api/campaigns", "/api/posts"):
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
            if path == "/api/campaigns":
                return self.reply({"campaign": add_campaign(DATA, payload)}, 201)
            if path == "/api/posts":
                return self.reply({"post": add_post(DATA, payload)}, 201)
            action = payload.get("action")
            if action not in ("trends", "streams", "analyze", "clip", "translate", "check", "live"):
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
