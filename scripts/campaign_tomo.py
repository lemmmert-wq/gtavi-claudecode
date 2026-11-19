#!/usr/bin/env python3
"""Prepare a PRIVATE GTA VI clipping campaign preview from a named Tomo video.

The public Content Rewards campaign explicitly identifies Tomo's own GTA VI
videos/streams as eligible source material. Users must join and review all
campaign terms before ever publishing. This script never publishes/joins.

Source: https://www.youtube.com/watch?v=w7OmfMXergI
Tomo unboxes a physical GTA 6 copy (~04:50 onwards, based on a public
third-party timestamp guide). Timestamp is an EDITORIAL STARTING POINT,
not a claim that the exact shot is there; always review the generated preview.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOB = ROOT / "jobs" / "tomo-unboxing"
SRC = "https://www.youtube.com/watch?v=w7OmfMXergI"
CAMPAIGN = "https://contentrewards.com/c/campaigns/df6de26f-86ec-4782-b818-1fc8053b99a4"
CUT_FROM = "00:04:48"
CUT_TO = "00:05:12"
HOOK = "HE OPENED GTA 6... WHERE'S THE DISC?"

def run(cmd, timeout=900):
    p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, errors="replace", timeout=timeout)
    if p.returncode:
        raise RuntimeError((p.stdout or "Onbekende fout")[-1800:])
    return p.stdout

def build():
    JOB.mkdir(parents=True, exist_ok=True)
    target = JOB / "source.mp4"
    meta_file = JOB / "source-info.json"
    print("1/4: Video-eigenaar en beschikbaarheid controleren...", flush=True)
    result = run([sys.executable, "-m", "yt_dlp", "--no-playlist",
                  "--skip-download", "--dump-single-json", SRC], 80)
    info = json.loads(result)
    uploader = " ".join(str(info.get(k) or "") for k in
                        ("channel", "uploader", "uploader_id")).lower()
    if "tomo" not in uploader:
        raise RuntimeError("Videobron lijkt niet afkomstig van Tomo. Bewerking gestopt.")
    if info.get("is_live") or info.get("live_status") == "is_live":
        raise RuntimeError("De bron is nog live. Kies eerst een afgeronde video.")
    meta_file.write_text(json.dumps({
        "title": info.get("title"), "channel": info.get("channel"),
        "source": SRC, "campaign": CAMPAIGN, "preview_only": True
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    if not target.exists() or target.stat().st_size < 10000:
        print("2/4: Alleen het korte bronfragment ophalen...", flush=True)
        # Keep the source clip short: do not download the entire creator VOD.
        run([sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-progress",
             "--download-sections", "*"+CUT_FROM+"-"+CUT_TO,
             "-f", "bv*[height<=720]+ba/b[height<=720]/b",
             "--merge-output-format", "mp4", "-o", str(target), SRC], 600)
    if not target.is_file() or target.stat().st_size < 10000:
        raise RuntimeError("Geen MP4 gedownload. Video kan afgeschermd of geblokkeerd zijn.")

    from scripts.common import ffprobe
    duration = float(ffprobe(target)["format"]["duration"])
    if not 8 <= duration <= 40:
        raise RuntimeError(f"Onverwachte fragmentduur ({duration:.1f}s). Preview niet gemaakt.")
    # Don't invent what was said: captions are only made from actual audio.
    print("3/4: Engelse audio herkennen en ondertitels maken...", flush=True)
    from scripts.moments import audio_rms
    wav, _ = audio_rms(target, JOB)
    try:
        import wave
        import numpy as np
        from faster_whisper import WhisperModel
        with wave.open(str(wav)) as w:
            sound = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(sound, word_timestamps=True, language="en",
                                       vad_filter=True)
        words = [{"w": word.word.strip(), "s": round(word.start, 2),
                  "e": round(word.end, 2)}
                 for segment in segments for word in (segment.words or [])
                 if word.word.strip()]
    except Exception as exc:
        print("Whisper niet beschikbaar; preview wordt zonder verzonnen ondertitels gemaakt: "
              + str(exc)[:250], flush=True)
        words = []
    (JOB / "transcript.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    end = min(duration, 21.0)
    (JOB / "candidates.json").write_text(json.dumps({
        "source": str(target),
        "info": {"title": "Tomo — GTA 6 fysieke doos (PRIVÉCONCEPT)",
                 "channel": "Tomo", "webpage_url": SRC},
        "duration": duration,
        "candidates": [{
            "n": 1, "start": 0.0, "end": end, "peak": 0,
            "score": 0, "why": ["handmatig gekozen videomoment — nog beoordelen"],
            "text": " ".join(w["w"] for w in words)[:400]}],
        "signals": {"heatmap": False, "chat": False, "words": len(words)}
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("4/4: 9:16 conceptclip maken...", flush=True)
    run([sys.executable, "scripts/cut.py", str(JOB), "--pick", "1",
         "--layout", "blur", "--captions", "word" if words else "none",
         "--hook", HOOK, "--preset", "veryfast"], 800)
    output = JOB / "edits" / "clip_1.mp4"
    if not output.exists() or output.stat().st_size < 10000:
        raise RuntimeError("FFmpeg heeft geen bruikbaar clipbestand aangemaakt.")
    print("PRIVÉCONCEPT GEREED: jobs/tomo-unboxing/edits/clip_1.mp4", flush=True)
    print("Niet publiceren of indienen vóór campagne-aanmelding, controle van voorwaarden "
          "en handmatige review van inhoud en timing.", flush=True)

if __name__ == "__main__":
    try:
        build()
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("TOMO-CONCEPT MISLUKT: " + str(error), file=sys.stderr, flush=True)
        sys.exit(1)
