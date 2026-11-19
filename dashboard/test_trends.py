"""Offline tests for the GTA trend search and freshness labels."""
import unittest
from datetime import datetime, timezone
from scripts.trends import canonical_url, collect, render


class TrendSearchTests(unittest.TestCase):
    def test_canonical_url_uses_youtube_id(self):
        self.assertEqual(canonical_url({"id": "abcdefghijk", "url": "abcdefghijk"}),
                         "https://www.youtube.com/watch?v=abcdefghijk")
        self.assertIsNone(canonical_url({"url": "https://www.youtube.com/shorts/abcdefghijk"}))
        self.assertIsNone(canonical_url({"url": "https://malicious.example/watch?v=abcdefghijk"}))

    def test_recent_and_unverified_videos_are_separated(self):
        now = datetime(2026, 11, 19, 15, 0, tzinfo=timezone.utc).timestamp()
        ids = ["abcdefghijk", "mnopqrstuvw", "0123456789_", "zzzzzzzzzzz"]
        def search(*_args):
            return {"entries": [{"id": vid, "title": "GTA 6 clip " + vid,
                                 "view_count": 420} for vid in ids]}
        info = {
            ids[0]: {"timestamp": now - 3600, "view_count": 1000, "title": "Verified recent"},
            ids[1]: {"upload_date": "20261119", "view_count": 2000, "title": "Only day"},
            ids[2]: {"view_count": 3000, "title": "No date"},
            ids[3]: {"timestamp": now - 172800, "view_count": 9999, "title": "Old"},
        }
        def fetch(url):
            return info[url.rsplit("=", 1)[-1]]
        rows, meta = collect("gta 6", 24, 12, lookup=search, fetch=fetch, now=now)
        self.assertEqual([x["freshness"] for x in rows], ["exact", "day", "unknown"])
        self.assertAlmostEqual(rows[0]["views_per_hour"], 1000, places=0)
        self.assertIsNone(rows[1]["views_per_hour"])
        self.assertIsNone(rows[2]["age_hours"])
        self.assertEqual(meta["searched"], 4)
        report = render(rows, "gta 6", 24, meta)
        self.assertIn("Bevestigd binnen", report)
        self.assertIn("geen bewezen trends", report.lower())

    def test_no_details_does_not_discard_search_results(self):
        now = datetime(2026, 11, 19, 15, 0, tzinfo=timezone.utc).timestamp()
        rows, meta = collect("gta 6", 24, 2,
                             lookup=lambda *_: {"entries": [{"id": "abcdefghijk", "title": "GTA 6 video"}]},
                             fetch=lambda *_: None, now=now)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["freshness"], "unknown")
        self.assertEqual(meta["details_failed"], 1)


if __name__ == "__main__":
    unittest.main()
