"""Search YouTube for GTA 6 videos without silently dropping undated results.

Videos with an exact timestamp and verified age <= hours are ranked by views
per hour. Date-only / undated videos are clearly separated and NOT presented as
confirmed trends. Writes a Markdown report and a JSON sidecar for the phone UI.
"""
import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).parent))
from common import ytdlp_json

UPLOAD_DATE_SORT = "&sp=CAI%253D"
VIDEO_ID = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def canonical_url(entry):
    raw = str(entry.get("url") or "").strip()
    video_id = str(entry.get("id") or "").strip()
    if "/shorts/" in raw:
        return None
    if VIDEO_ID.fullmatch(video_id):
        return "https://www.youtube.com/watch?v=" + video_id
    if VIDEO_ID.fullmatch(raw):
        return "https://www.youtube.com/watch?v=" + raw
    if raw.startswith(("https://www.youtube.com/watch?", "https://youtube.com/watch?", "https://youtu.be/")):
        return raw
    return None


def detail(url):
    try:
        return ytdlp_json(url, ["--skip-download"])
    except (SystemExit, ValueError, OSError):
        return None


def date_from_meta(item):
    """Return (timestamp, precision) or (None, 'unknown')."""
    for key in ("timestamp", "release_timestamp"):
        try:
            t = float(item.get(key) or 0)
            if 0 < t <= time.time() + 86400:
                return t, "exact"
        except (TypeError, ValueError):
            pass
    date = str(item.get("upload_date") or "")
    if re.fullmatch(r"\d{8}", date):
        try:
            midnight = datetime.strptime(date, "%Y%m%d").replace(tzinfo=timezone.utc)
            return midnight.timestamp(), "day"
        except ValueError:
            pass
    return None, "unknown"


def identify(flat, info, url, now, hours):
    """Produce an item with an explicit freshness classification, or None."""
    data = info or {}
    if data.get("is_live") or flat.get("is_live"):
        return None
    if data.get("live_status") == "is_live":
        return None
    # Prefer detailed metadata, but fall back to the flat search entry.
    timestamp, precision = date_from_meta(data)
    if timestamp is None:
        timestamp, precision = date_from_meta(flat)
    age = (now - timestamp) / 3600 if timestamp is not None else None
    if precision == "exact" and (age is None or age < -0.5 or age > hours):
        return None
    if precision == "day":
        # We know only the UTC calendar date, not the hour of publishing.
        # Include boundary days when they might overlap the requested window.
        if timestamp + 86400 < now - hours * 3600 or timestamp > now:
            return None
    try:
        views = int(data.get("view_count") or flat.get("view_count") or 0)
    except (ValueError, TypeError):
        views = 0
    view_rate = round(views / max(age, 0.25), 1) if precision == "exact" and age is not None else None
    title = str(data.get("title") or flat.get("title") or "Video zonder titel")
    channel = str(data.get("channel") or data.get("uploader") or flat.get("channel") or flat.get("uploader") or "")
    return {"title": title, "url": url, "channel": channel, "views": views,
            "age_hours": round(age, 1) if precision == "exact" else None,
            "views_per_hour": view_rate, "freshness": precision}


def collect(query, hours, limit, lookup=ytdlp_json, fetch=detail, now=None):
    now = time.time() if now is None else now
    q = quote_plus(query)
    try:
        search = lookup("https://www.youtube.com/results?search_query=" + q + UPLOAD_DATE_SORT,
                        ["--flat-playlist", "--playlist-end", str(limit)])
    except (SystemExit, ValueError, OSError):
        search = {"entries": []}
    entries = []
    seen = set()
    for e in (search or {}).get("entries") or []:
        if not isinstance(e, dict):
            continue
        url = canonical_url(e)
        if url and url not in seen:
            entries.append((e, url))
            seen.add(url)
    if not entries:
        return [], {"searched": 0, "details_failed": 0}
    with ThreadPoolExecutor(max_workers=min(5, len(entries))) as pool:
        infos = list(pool.map(fetch, [url for _, url in entries]))
    details_failed = sum(i is None for i in infos)
    rows = [identify(e, i, url, now, hours) for (e, url), i in zip(entries, infos)]
    rows = [r for r in rows if r is not None]
    # Exact timestamps first; day-only next; unknown last. Never treat an
    # unknown-age result as having a calculated views/hour score.
    rank = {"exact": 0, "day": 1, "unknown": 2}
    rows.sort(key=lambda r: (rank[r["freshness"]], -(r["views_per_hour"] or 0) if r["freshness"] == "exact" else -r["views"]))
    return rows[:limit], {"searched": len(entries), "details_failed": details_failed}


def render(rows, query, hours, meta):
    exact = [r for r in rows if r["freshness"] == "exact"]
    other = [r for r in rows if r["freshness"] != "exact"]
    report = [f"# GTA 6-videozoeker · {query} · {hours:g} uur",
              f"Gecontroleerd: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}.",
              ""]
    if exact:
        report += ["## Bevestigd binnen de zoekperiode", "",
                   "| Views/uur | Views | Leeftijd | Kanaal | Video |",
                   "|---:|---:|---:|---|---|"]
        for r in exact:
            title = r["title"].replace("|", "/").replace("\n", " ")[:110]
            report.append(f'| {r["views_per_hour"]:,.0f} | {r["views"]:,} | {r["age_hours"]:.1f}u | {r["channel"].replace("|", "/")} | [{title}]({r["url"]}) |')
    else:
        report += ["Geen video's met een **bevestigd exact publicatietijdstip** binnen de gekozen periode.", ""]
    if other:
        report += ["", "## Andere gevonden video's — recente publicatie niet bevestigd", "",
                   "Dit zijn zoeksuggesties, **geen bewezen trends**. Controleer de publicatiedatum op YouTube.", ""]
        for r in other[:10]:
            note = "dag bekend, uur onbekend" if r["freshness"] == "day" else "publicatiedatum onbekend"
            report.append(f'- [{r["title"][:100]}]({r["url"]}) — {r["channel"]} · {r["views"]:,} views · {note}')
    if not rows:
        report += ["", "Geen bruikbare video's gevonden. YouTube kan tijdelijk beperkte metadata teruggeven, of de gekozen zoekperiode bevat geen passende video's."]
    if meta["details_failed"]:
        report += ["", f'Let op: voor {meta["details_failed"]} video(s) kon YouTube geen volledige details leveren.']
    if not meta["searched"]:
        report += ["", "De YouTube-zoekopdracht leverde geen videoverwijzingen op. Probeer later opnieuw."]
    report += ["", "Dit overzicht geeft geen toestemming om beelden te herpubliceren."]
    return "\n".join(report) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="gta 6")
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--out", default="trends.md")
    args = ap.parse_args()
    rows, meta = collect(args.query, args.hours, args.limit)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(rows, args.query, args.hours, meta), encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps({"items": rows, "meta": meta}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f'{len(rows)} videos ({sum(r["freshness"] == "exact" for r in rows)} exact recent); '
          f'{meta["searched"]} search hits; {meta["details_failed"]} detail lookups failed.')
    print(f'Resultaten: {out}')


if __name__ == "__main__":
    main()
