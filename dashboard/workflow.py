"""Private local campaign and published-post records for the mobile dashboard.

Campaign terms and payouts are human-entered. Never claim an unverified offer
is live, never infer a missing rate, and never treat projected payouts as earned.
Records are held in the Codespace's ignored .dashboard directory.
"""
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

STORE_LOCK = threading.RLock()
ALLOWED_STATES = {"posted", "submitted", "approved", "paid"}


def clean(value, limit=300):
    return str(value or "").strip()[:limit]


def https_link(value, required=True):
    value = clean(value, 1000)
    if not value and not required:
        return ""
    try:
        u = urlparse(value)
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            raise ValueError()
        if u.port and u.port not in (443,):
            raise ValueError()
    except ValueError:
        raise ValueError("Gebruik een volledige https://-link")
    return value


def nonnegative_number(value, label, maximum=10000000, optional=True):
    if value in (None, "") and optional:
        return None
    try:
        number = float(value)
        if number < 0 or number > maximum or not (number < float("inf")):
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError(f"Ongeldig veld: {label}")
    return round(number, 4)


def read_records(folder, name):
    path = Path(folder) / name
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def write_records(folder, name, values):
    path = Path(folder) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(values, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def list_campaigns(folder):
    with STORE_LOCK:
        return read_records(folder, "campaigns.json")


def list_posts(folder):
    with STORE_LOCK:
        return read_records(folder, "posts.json")


def get_campaign(folder, campaign_id):
    if not campaign_id:
        return None
    return next((c for c in list_campaigns(folder) if c["id"] == campaign_id), None)


def add_campaign(folder, data):
    name = clean(data.get("name"), 130)
    if not name:
        raise ValueError("Geef de campagne een naam")
    source_url = https_link(data.get("source_url"))
    terms = clean(data.get("rules"), 5000)
    reviewed = data.get("rules_reviewed") is True
    min_seconds = nonnegative_number(data.get("min_seconds"), "minimumduur", 3600)
    max_seconds = nonnegative_number(data.get("max_seconds"), "maximumduur", 3600)
    if min_seconds is not None and max_seconds is not None and min_seconds > max_seconds:
        raise ValueError("Maximumduur moet groter zijn dan minimumduur")
    rate = nonnegative_number(data.get("rate_per_1k"), "bedrag per 1.000 views")
    cap = nonnegative_number(data.get("cap_per_clip"), "maximum per clip")
    currency = clean(data.get("currency") or "USD", 3).upper()
    if currency not in {"USD", "EUR", "GBP"}:
        raise ValueError("Kies USD, EUR of GBP")
    obj = {
        "id": uuid.uuid4().hex[:12], "name": name,
        "creator": clean(data.get("creator"), 120),
        "source_url": source_url,
        "source_material": clean(data.get("source_material"), 400),
        "platforms": clean(data.get("platforms"), 120),
        "rate_per_1k": rate, "currency": currency, "cap_per_clip": cap,
        "budget_left": clean(data.get("budget_left"), 80),
        "rules": terms, "rules_reviewed": reviewed,
        "min_seconds": min_seconds, "max_seconds": max_seconds,
        "required_hashtags": clean(data.get("required_hashtags"), 150),
        "required_mention": clean(data.get("required_mention"), 100),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "handmatig vastgelegd; actuele beschikbaarheid niet bevestigd",
    }
    with STORE_LOCK:
        entries = read_records(folder, "campaigns.json")
        entries.insert(0, obj)
        write_records(folder, "campaigns.json", entries[:100])
    return obj


def campaign_rules_file(folder, campaign):
    """Create a minimal rules file for the original check.py script.

    Other campaign conditions (allowed creator, overlays, credit, approval,
    country eligibility) cannot be checked with the original technical checker.
    """
    if not campaign or not campaign.get("rules_reviewed"):
        return None
    parts = [f"# {campaign['name']}", "## Manually transcribed rules"]
    if campaign.get("min_seconds") is not None:
        parts += [f"min_seconds: {campaign['min_seconds']}"]
    if campaign.get("max_seconds") is not None:
        parts += [f"max_seconds: {campaign['max_seconds']}"]
    tags = re.findall(r"#[\w]+", campaign.get("required_hashtags") or "")
    if tags:
        parts += ["required_hashtags: " + " ".join(tags)]
    mentions = re.findall(r"@[\w]+", campaign.get("required_mention") or "")
    if mentions:
        parts += ["required_mention: " + mentions[0]]
    rules_dir = Path(folder) / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    path = rules_dir / (campaign["id"] + ".md")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


def add_post(folder, data):
    url = https_link(data.get("url"))
    state = clean(data.get("state") or "posted", 16)
    if state not in ALLOWED_STATES:
        raise ValueError("Onbekende publicatiestatus")
    views = nonnegative_number(data.get("views"), "views", 1000000000)
    if views is not None and views != int(views):
        raise ValueError("Aantal views moet geheel zijn")
    payout = nonnegative_number(data.get("confirmed_payout"), "bevestigd bedrag")
    if payout is not None and state not in ("approved", "paid"):
        raise ValueError("Bevestigde opbrengsten alleen bij goedgekeurd of betaald")
    campaign_id = clean(data.get("campaign_id"), 12)
    if campaign_id and not get_campaign(folder, campaign_id):
        raise ValueError("Campagne niet gevonden")
    currency = clean(data.get("currency") or "USD", 3).upper()
    if currency not in {"USD", "EUR", "GBP"}:
        raise ValueError("Onbekende munt")
    checkpoint = clean(data.get("checkpoint") or "other", 8)
    if checkpoint not in ("12h", "24h", "72h", "other"):
        raise ValueError("Onbekend meetmoment")
    now = datetime.now(timezone.utc).isoformat()
    with STORE_LOCK:
        entries = read_records(folder, "posts.json")
        old = next((p for p in entries if p.get("url") == url), None)
        if old:
            stages = ["posted", "submitted", "approved", "paid"]
            if stages.index(state) < stages.index(old["state"]):
                raise ValueError("Een gepubliceerde clip kan niet terug naar een eerdere status")
            if payout is None and old["state"] in ("approved", "paid") and state in ("approved", "paid"):
                payout = old.get("confirmed_payout")
        obj = {
            "id": old["id"] if old else uuid.uuid4().hex[:12],
            "url": url, "platform": clean(data.get("platform"), 30),
            "campaign_id": campaign_id or (old.get("campaign_id", "") if old else ""),
            "views": int(views) if views is not None else (old.get("views") if old else None),
            "state": state, "confirmed_payout": payout, "currency": currency,
            "notes": clean(data.get("notes"), 400),
            "recorded_at": old["recorded_at"] if old else now,
            "updated_at": now,
            "history": (old.get("history", []) if old else [])[-19:] + [{
                "at": now, "checkpoint": checkpoint, "state": state,
                "views": int(views) if views is not None else None,
                "confirmed_payout": payout,
            }],
        }
        entries = [obj] + [p for p in entries if p.get("url") != url]
        write_records(folder, "posts.json", entries[:500])
    return obj
