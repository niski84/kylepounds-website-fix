import datetime as dt
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
import build_news
import inject_banner


class NewsTest(unittest.TestCase):
    def test_replaces_legacy_header_idempotently_without_losing_page_content(self):
        before = '<html><head><title>Ancient history</title><meta name="color-scheme" content="light"></head><body><!-- Kyle Pounce Banner -->\n<div style="color:red"><span>Adobe fonts working</span></div>\n<script>oldBanner()</script><h1>Original article</h1></body></html>'
        banner = build_news.header(build_news.posts(dt.date(2026, 11, 1)))
        first = inject_banner.transform(before, banner)
        self.assertEqual(first, inject_banner.transform(first, banner))
        self.assertIn('<h1>Original article</h1>', first)
        self.assertNotIn('oldBanner()', first)
        self.assertNotIn('Adobe fonts working', first)
        self.assertEqual(first.count('class="kp-header"'), 1)
        self.assertEqual(first.count('kp-news-assets:start'), 1)

    def test_expired_announcement_leaves_permanent_article_available(self):
        p = {'slug':'old-event', 'announcement':'Outdated event', 'announcement_until':'2026-10-30'}
        header = build_news.header([p], today=dt.date(2026, 11, 1))
        self.assertNotIn('Outdated event', header)
        self.assertIn('href="/news/"', header)

    def test_build_keeps_static_public_permalink_and_share_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            build_news.build(root)
            page = Path(root, 'news/the-archive-has-a-podcast/index.html').read_text()
            self.assertIn('<link rel="canonical" href="https://kylepounds.org/news/the-archive-has-a-podcast/">', page)
            self.assertIn('https://kylepounds.org/patrol/api/podcasts/feed.xml', page)
            self.assertIn('data-copy-link', page)
            self.assertIn('AI generated', page)
            self.assertIn('prefers-color-scheme:dark', page)
            self.assertEqual(page, inject_banner.transform(page, build_news.header(build_news.posts())))


if __name__ == '__main__':
    unittest.main()
