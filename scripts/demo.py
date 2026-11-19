#!/usr/bin/env python3
"""Generate an ORIGINAL local video and verify the genuine GTA Clipper workflow.

This tests FFmpeg -> original scripts/cut.py -> scripts/check.py -> MP4,
without downloading or reusing any third-party material. No Whisper or online
campaign checks are claimed, and nothing gets published.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOB = ROOT / "jobs" / "demo-local"
SOURCE = JOB / "source.mp4"
CLIP = JOB / "edits" / "clip_1.mp4"
TRANSCRIPT = "Dit is een eigen proefclip gemaakt om het maken en bekijken van verticale video's te testen".split()
SECONDS = 9

def execute(args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                            errors="replace", timeout=600)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-2500:] or f"Programma stopte met code {result.returncode}")
    return result.stdout.strip()

def build():
    JOB.mkdir(parents=True, exist_ok=True)
    if not SOURCE.is_file() or SOURCE.stat().st_size < 10000:
        print("1/3: Eigen testvideo maken (zonder YouTube).", flush=True)
        execute(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24",
                 "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                 "-t", str(SECONDS), "-c:v", "libx264", "-preset", "ultrafast",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(SOURCE)])
    start, end = 0.25, 8.5
    words = []
    for i, word in enumerate(TRANSCRIPT):
        s = 0.45 + i * 0.44
        words.append({"w": word, "s": round(s, 2), "e": round(s + 0.39, 2)})
    (JOB / "transcript.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    (JOB / "candidates.json").write_text(json.dumps({
        "source": str(SOURCE),
        "info": {"title": "EIGEN PROEFCLIP - geen GTA 6 beelden",
                 "channel": "GTA Clipper Test", "webpage_url": ""},
        "duration": SECONDS,
        "candidates": [{"n": 1, "start": start, "end": end,
                        "score": 1, "why": ["eigen technische test"],
                        "text": " ".join(TRANSCRIPT)}],
        "signals": {"heatmap": False, "chat": False, "words": len(words)}
    }, ensure_ascii=False), encoding="utf-8")
    print("2/3: Werkelijke clipknipper gebruiken: 1080x1920 met ondertitels.", flush=True)
    execute([sys.executable, "scripts/cut.py", str(JOB), "--pick", "1",
             "--layout", "fill", "--captions", "word",
             "--hook", "PROEFCLIP - NIET PUBLICEREN", "--preset", "ultrafast"])
    if not CLIP.is_file() or CLIP.stat().st_size < 10000:
        raise RuntimeError("Er is geen bruikbaar MP4-bestand gemaakt")
    print("3/3: Clip controleren met originele scripts/check.py.", flush=True)
    check = execute([sys.executable, "scripts/check.py", str(CLIP),
                     "--caption", "Eigen technische proefclip, niet publiceren"])
    print(check, flush=True)
    print("TEST GESLAAGD. Bekijk 'Proefclip 1' in stap 5 van je dashboard.", flush=True)

if __name__ == "__main__":
    try:
        build()
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
        print("TEST MISLUKT: " + str(e), file=sys.stderr, flush=True)
        sys.exit(1)
