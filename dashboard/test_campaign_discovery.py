"""Offline checks for public campaign discovery.

Never hit real network during CI: the live site can change, require JS or
block server-to-server requests. Test HTML parsing and truthful fallback.
"""
import tempfile
import unittest
from pathlib import Path
from dashboard.campaign_discovery import (
    PublicPage, find_candidates, extract_details, discover, save_discovery, read_discovery
)

LINK = "https://contentrewards.com/c/campaigns/2eaa14fb-6927-4136-897e-b096e0d907d6"

def page(html):
    p = PublicPage()
    p.feed(html)
    return p

class PublicCampaignFinderTests(unittest.TestCase):
    def test_candidates_are_gta_only_and_external_links_are_skipped(self):
        p = page('<html><a href="/c/campaigns/2eaa14fb-6927-4136-897e-b096e0d907d6">'
                 '<span>ClipLaunch</span><b>KreekCraft GTA 6 Clipping</b></a>'
                 '<a href="https://evil.test/c/campaigns/2eaa14fb-6927-4136-897e-b096e0d907d6">GTA 6</a>'
                 '<a href="/c/campaigns/1eaa14fb-6927-4136-897e-b096e0d907d6">Podcast</a>'
                 '</html>')
        items = find_candidates(p)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], LINK)

    def test_public_rate_only_and_active_status(self):
        p = page('<html><h1>KreekCraft GTA 6 Clipping</h1>'
                 '<p>Accepting clips</p><div>TikTok</div>'
                 '<div>Per 1K views</div><span>$1.00</span>'
                 '<div>Max payout</div><span>$300.00</span>'
                 '<div>$6,824 still up for grabs</div></html>')
        got = extract_details({"url": LINK,"listing_text":"KreekCraft GTA 6"}, fetch=lambda _: p)
        self.assertEqual(got["name"], "KreekCraft GTA 6 Clipping")
        self.assertEqual(got["status"], "accepteert clips volgens publieke pagina")
        self.assertEqual(got["rate_per_1k"], 1)
        self.assertEqual(got["max_per_clip"], 300)
        self.assertEqual(got["remaining_budget"], 6824)

    def test_unavailable_fields_are_unknown(self):
        p = page('<html><h1>My GTA VI campaign</h1><p>Join to see details</p></html>')
        got = extract_details({"url": LINK,"listing_text":"My GTA VI campaign"}, fetch=lambda _: p)
        self.assertIsNone(got["rate_per_1k"])
        self.assertIsNone(got["remaining_budget"])
        self.assertEqual(got["status"], "onbekend")

    def test_discovery_handles_unreachable_detail_page(self):
        listing = page('<html><a href="'+LINK+'">KreekCraft GTA 6 Clipping</a></html>')
        def mock_fetch(url):
            if "/discover" in url:
                return listing
            raise OSError("connection refused")
        found = discover(fetch=mock_fetch)
        self.assertEqual(found["items"], [])
        self.assertEqual(found["failed"], 1)
        with tempfile.TemporaryDirectory() as directory:
            save_discovery(Path(directory), found)
            self.assertEqual(read_discovery(Path(directory))["failed"], 1)

    def test_empty_listing_fails_honestly(self):
        with self.assertRaises(RuntimeError):
            discover(fetch=lambda _: page('<html><p>Loading...</p></html>'))


if __name__ == "__main__":
    unittest.main()
