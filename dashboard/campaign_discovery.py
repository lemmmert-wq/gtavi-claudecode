"""Read-only discovery of publicly listed GTA 6 clipping campaigns.

No account access, scraping behind a login, or claim of acceptance/eligibility.
Results are suggestions; users must join and review the complete campaign brief.
External site layouts can change; errors are surfaced instead of guessed data.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

LISTING_URL = "https://contentrewards.com/c/discover"
DOMAIN = "contentrewards.com"
CAMPAIGN_PATH = re.compile(r"^/c/campaigns/([0-9a-fA-F-]{36})/?$")
KEYWORDS = ("gta 6", "gta vi", "gtavi", "grand theft auto", "gta6")
USER_AGENT = "Mozilla/5.0 (compatible; GTAClipper/1.0; public-campaign-discovery)"


class PublicPage(HTMLParser):
    """Extract public text, headings, meta descriptions, and campaign links."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.text = []
        self.links = []
        self.active_link = None
        self.in_h1 = False
        self.h1 = []
        self.description = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if self.skip:
            return
        if tag == "h1":
            self.in_h1 = True
        if tag == "meta" and a.get("name", "").lower() == "description":
            self.description = a.get("content", "")[:500]
        if tag == "a" and a.get("href"):
            self.active_link = {"href": a["href"], "label": []}

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "h1":
            self.in_h1 = False
        if tag == "a" and self.active_link:
            self.links.append((self.active_link["href"], " ".join(self.active_link["label"])))
            self.active_link = None
        if tag in ("p", "div", "h1", "h2", "h3", "li", "section", "span", "br"):
            self.text.append(" ")

    def handle_data(self, data):
        if self.skip:
            return
        x = data.strip()
        if not x:
            return
        self.text.append(x)
        if self.in_h1:
            self.h1.append(x)
        if self.active_link:
            self.active_link["label"].append(x)

    def combined_text(self):
        return re.sub(r"\s+", " ", unescape(" ".join(self.text))).strip()


def fetch_page(url, timeout=9):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in (DOMAIN, "www." + DOMAIN):
        raise ValueError("Ongeldige campagnebron")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(request, timeout=timeout) as response:
        # Bound response size; pages can have huge embedded JSON.
        html = response.read(2_000_000).decode("utf-8", errors="replace")
    if "<html" not in html.lower() and "<!doctype" not in html.lower():
        raise ValueError("Geen leesbare openbare campagnepagina ontvangen")
    p = PublicPage()
    p.feed(html)
    return p


def canonical_campaign_url(href):
    absolute = urljoin(LISTING_URL, href)
    u = urlparse(absolute)
    if u.scheme != "https" or u.hostname not in (DOMAIN, "www." + DOMAIN):
        return None
    if not CAMPAIGN_PATH.fullmatch(u.path):
        return None
    return "https://contentrewards.com" + u.path.rstrip("/")


def find_candidates(page, max_candidates=18):
    candidates = []
    seen = set()
    for href, label in page.links:
        url = canonical_campaign_url(href)
        if not url or url in seen:
            continue
        seen.add(url)
        title = re.sub(r"\s+", " ", label).strip()[:260]
        if any(word in title.lower() for word in KEYWORDS):
            candidates.append({"url": url, "listing_text": title})
        if len(candidates) >= max_candidates:
            break
    return candidates


def currency_value(text):
    if not text:
        return None
    try:
        val = float(text.replace(",", ""))
        return val if val >= 0 else None
    except ValueError:
        return None


def extract_details(candidate, fetch=fetch_page):
    page = fetch(candidate["url"])
    text = page.combined_text()
    name = " ".join(page.h1).strip()
    if not name:
        name = candidate["listing_text"]
    if not any(w in (name + " " + page.description + " " + candidate["listing_text"]).lower()
               for w in KEYWORDS):
        return None
    status = "onbekend"
    if re.search(r"\b(?:Closed|Ended|Not accepting clips|Campaign completed)\b", text, re.I):
        status = "niet actief volgens publieke pagina"
    elif re.search(r"\bAccepting clips\b", text, re.I):
        status = "accepteert clips volgens publieke pagina"
    # Read only amounts that are labelled on the publicly accessible campaign page.
    rate_match = re.search(r"Per\s*1K\s*views\s*\$\s*([\d,]+(?:\.\d+)?)", text, re.I)
    max_match = re.search(r"Max\s*payout\s*\$\s*([\d,]+(?:\.\d+)?)", text, re.I)
    budget_match = re.search(r"\$\s*([\d,]+(?:\.\d+)?)\s+still up for grabs", text, re.I)
    if not budget_match:
        # This fallback is intentionally omitted: $spent/$total does not
        # guarantee that the remainder is available to new participants.
        pass
    platforms = [name for name in ("TikTok", "Instagram", "YouTube", "X", "Facebook")
                 if re.search(r"\b" + re.escape(name) + r"\b", text)]
    return {
        "name": name[:160],
        "url": candidate["url"],
        "platforms": platforms,
        "rate_per_1k": currency_value(rate_match.group(1)) if rate_match else None,
        "currency": "USD",
        "max_per_clip": currency_value(max_match.group(1)) if max_match else None,
        "remaining_budget": currency_value(budget_match.group(1)) if budget_match else None,
        "status": status,
        "summary": page.description[:260] or "",
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rules_warning": "Bekijk alle voorwaarden, toegestane bronnen en Belgische deelname na aanmelden.",
    }


def discover(query="gta", fetch=fetch_page):
    if query != "gta":
        raise ValueError("Onbekende campagneselectie")
    listing = fetch(LISTING_URL)
    candidates = find_candidates(listing, max_candidates=18)
    if not candidates:
        raise RuntimeError("De publieke campagnepagina geeft geen herkenbare GTA 6-campagnelinks terug. Open de bronwebsite rechtstreeks.")
    # Public campaign details, never login pages or private API endpoints.
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(extract_details, item, fetch) for item in candidates]
        results, failed = [], 0
        for future in futures:
            try:
                value = future.result(timeout=45)
                if value:
                    results.append(value)
            except Exception:
                failed += 1
    results.sort(key=lambda x: (x["status"] != "accepteert clips volgens publieke pagina",
                                -(x["rate_per_1k"] or 0), x["name"].lower()))
    return {
        "source": LISTING_URL,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": results,
        "failed": failed,
        "notice": "Automatische openbare zoekresultaten. Geen garantie op campagnebeschikbaarheid, toestemming, Belgische deelname of uitbetaling.",
    }


def save_discovery(folder, result):
    dest = Path(folder) / "discovered_campaigns.json"
    dest.parent.mkdir(exist_ok=True, parents=True)
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(dest)
    return dest


def read_discovery(folder):
    p = Path(folder) / "discovered_campaigns.json"
    if not p.exists():
        return {"items": [], "checked_at": "", "notice": "Nog geen zoekopdracht gestart"}
    return json.loads(p.read_text(encoding="utf-8"))
