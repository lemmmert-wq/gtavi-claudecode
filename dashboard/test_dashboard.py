import unittest
from dashboard.app import valid_url


class DashboardValidationTests(unittest.TestCase):
    def test_allowed_links(self):
        self.assertTrue(valid_url("https://www.youtube.com/watch?v=abcdefghijk"))
        self.assertTrue(valid_url("https://youtu.be/abcdefghijk"))
        self.assertTrue(valid_url("https://www.twitch.tv/videos/123456"))

    def test_rejects_unapproved_urls(self):
        for url in (
            "http://youtube.com/watch?v=abcdefghijk",
            "https://youtube.com.evil.test/watch?v=abcdefghijk",
            "https://127.0.0.1/private",
            "file:///etc/passwd",
            "https://example.com/video.mp4",
            "",
        ):
            with self.subTest(url=url):
                self.assertFalse(valid_url(url))


if __name__ == "__main__":
    unittest.main()
