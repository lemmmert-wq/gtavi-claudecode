"""Offline regression tests for original-plugin mobile workflow."""
import tempfile
import unittest
from pathlib import Path

from dashboard.workflow import (
    add_campaign, add_post, campaign_rules_file, get_campaign,
    list_campaigns, list_posts, https_link,
)


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_campaign_rates_are_optional_and_rules_require_human_review(self):
        saved = add_campaign(self.folder, {
            "name": "Streamer clip campagne",
            "source_url": "https://contentrewards.com/c/campaigns/abc123",
            "rate_per_1k": "",
            "min_seconds": 10,
            "max_seconds": 40,
            "required_hashtags": "#GTA6 #Streamer",
            "required_mention": "@Streamer",
            "rules": "Only approved footage",
            "rules_reviewed": True,
        })
        self.assertIsNone(saved["rate_per_1k"])
        self.assertIsNotNone(get_campaign(self.folder, saved["id"]))
        self.assertEqual(len(list_campaigns(self.folder)), 1)
        text = campaign_rules_file(self.folder, saved).read_text()
        self.assertIn("min_seconds: 10.0", text)
        self.assertIn("max_seconds: 40.0", text)
        self.assertIn("#GTA6 #Streamer", text)
        self.assertIn("@Streamer", text)

    def test_unreviewed_campaign_cannot_generate_rules_file(self):
        saved = add_campaign(self.folder, {
            "name": "Ongelezen voorwaarden",
            "source_url": "https://example.org/rules",
            "rules_reviewed": False,
        })
        self.assertIsNone(campaign_rules_file(self.folder, saved))

    def test_invalid_url_disallowed(self):
        for url in ("javascript:alert(1)", "http://example.com", "https://user:pass@example.com"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    https_link(url)

    def test_post_revenue_only_confirmed_after_approval(self):
        payload = {"url": "https://www.tiktok.com/@a/video/123",
                   "platform": "TikTok", "views": 12500,
                   "state": "posted", "confirmed_payout": "5"}
        with self.assertRaises(ValueError):
            add_post(self.folder, payload)
        payload["state"] = "paid"
        saved = add_post(self.folder, payload)
        self.assertEqual(saved["confirmed_payout"], 5)
        self.assertEqual(list_posts(self.folder)[0]["state"], "paid")

    def test_campaign_does_not_accept_fictional_negative_rate(self):
        with self.assertRaises(ValueError):
            add_campaign(self.folder, {
                "name": "Bad",
                "source_url": "https://example.com/campaign",
                "rate_per_1k": "-3",
            })


if __name__ == "__main__":
    unittest.main()
