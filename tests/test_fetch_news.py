"""Offline fetching tests. Never invoke either newsletter pipeline."""

import copy
import io
import json
import unittest
from collections import Counter
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from xml.sax.saxutils import escape, quoteattr

import requests

import fetch_news as news


NOW = datetime(2026, 10, 9, 12, tzinfo=news.IST)
RECENT = "2026-10-09T05:00:00Z"
OLD = "2026-09-01T05:00:00Z"
FIELDS = {"title", "source", "description", "published_at", "link", "summary", "category"}
CONFIG = json.loads(news.CONFIG_PATH.read_text(encoding="utf-8"))


def article(index=1, source="Publisher", **overrides):
    result = news._article(f"Python story {index}", source, "Technical details. " * 12,
                           RECENT, f"https://example.com/{index}")
    result.update(overrides)
    return result


def rss(items):
    entries = []
    for item in items:
        entries.append("<item>" + "".join(
            f"<{key}>{escape(str(value))}</{key}>" for key, value in item.items()
        ) + "</item>")
    return ("<rss version='2.0'><channel><title>Feed</title>" + "".join(entries)
            + "</channel></rss>").encode()


def rss_item(index=1, **overrides):
    item = {"title": f"Python story {index}", "description": "<p>Technical &amp; useful details.</p>",
            "pubDate": "Fri, 09 Oct 2026 05:00:00 GMT", "link": f"https://example.com/{index}",
            "category": "Programming"}
    item.update(overrides)
    return item


def paper(index=1, **overrides):
    item = {"title": f"Language model reasoning {index}", "summary": "A study of efficient inference.",
            "published": RECENT, "updated": RECENT, "category": "cs.AI",
            "id": f"http://arxiv.org/abs/2610.{index:05}v1"}
    item.update(overrides)
    return item


def atom(items):
    entries = []
    for item in items:
        fields = "".join(f"<{key}>{escape(str(value))}</{key}>" for key, value in item.items()
                         if key not in {"category", "link"})
        category = f"<category term={quoteattr(item.get('category', 'cs.AI'))}/>"
        link = f"<link href={quoteattr(item.get('link', item['id']))} rel='alternate' type='text/html'/>"
        entries.append(f"<entry>{fields}{category}{link}</entry>")
    return ("<feed xmlns='http://www.w3.org/2005/Atom'><title>Research</title>"
            + "".join(entries) + "</feed>").encode()


def hn_item(index=1, **overrides):
    item = {"id": index, "type": "story", "title": f"Python compiler improvement {index}",
            "url": f"https://example.com/hn/{index}", "score": 100, "descendants": 25,
            "time": int(datetime(2026, 10, 9, 5, tzinfo=timezone.utc).timestamp())}
    item.update(overrides)
    return item


def release(index=1, **overrides):
    item = {"name": f"v1.{index}", "tag_name": f"v1.{index}", "draft": False,
            "prerelease": False, "published_at": RECENT, "body": "Improved inference performance.",
            "html_url": f"https://github.com/owner/project/releases/tag/v1.{index}"}
    item.update(overrides)
    return item


def response(body, status=200):
    result = requests.Response()
    result.status_code = status
    result.url = "https://mock.example/api"
    result._content = body if isinstance(body, bytes) else json.dumps(body).encode()
    result._content_consumed = True
    return result


class OfflineTest(unittest.TestCase):
    def setUp(self):
        self.config = copy.deepcopy(CONFIG)
        self.routes = {}
        self.get = self.enterContext(patch("requests.Session.get", side_effect=self.dispatch))
        self.enterContext(patch.object(news, "medium_feed_links", {}))

    def dispatch(self, url, **kwargs):
        if url not in self.routes:
            raise AssertionError(f"Unexpected request: {url}")
        result = self.routes[url]
        if isinstance(result, Exception):
            raise result
        return result if isinstance(result, requests.Response) else response(result)

    def collect(self, name):
        fetcher = {"rss": news.fetch_rss, "hacker_news": news.fetch_hacker_news,
                   "github": news.fetch_github_releases, "arxiv": news.fetch_arxiv,
                   "medium": news.fetch_medium}[name]
        return news._collect_source(name, fetcher, self.config[name], self.config["network"], NOW)

    def assert_shape(self, item):
        self.assertEqual(set(item), FIELDS)
        self.assertIsNone(item["summary"])
        self.assertIsInstance(item["published_at"], datetime)
        self.assertIsNone(item["published_at"].tzinfo)
        for field in ("title", "source", "description", "link"):
            self.assertIsInstance(item[field], str)
            self.assertTrue(item[field])

    def add_hn(self, items):
        self.routes[f"{news.HN_API}/topstories.json"] = list(range(1, len(items) + 1))
        self.routes.update({f"{news.HN_API}/item/{index}.json": item
                            for index, item in enumerate(items, 1)})


class TextCleaningTests(unittest.TestCase):
    def test_preserves_quotes_urls_and_technical_punctuation(self):
        text = 'What\u2019s new in "uv"? Visit https://github.com/astral-sh/uv. v1.2.3 uses std::io and ../cache.'
        self.assertEqual(news.clean_text(f"<p>{text}</p>"), text)

    def test_removes_markup_and_normalizes_word_separators(self):
        self.assertEqual(news.clean_text("<p>Paths\u200bwere\n verified &amp;\t tested.</p>"),
                         "Paths were verified & tested.")

    def test_preserves_non_ascii_text_and_emoji_joiners(self):
        text = "Caf\u00e9 \u2014 \u201cquoted\u201d \U0001f469\u200d\U0001f4bb"
        self.assertEqual(news.clean_text(text), text)


class DateAndUrlTests(unittest.TestCase):
    def test_date_formats_keep_existing_naive_ist_contract(self):
        expected = datetime(2026, 10, 9, 10, 30)
        for value in [RECENT, "Fri, 09 Oct 2026 05:00:00 GMT", "2026-10-09T07:00:00+02:00",
                      "2026-10-09T05:00:00", 1791522000]:
            with self.subTest(value=value):
                self.assertEqual(news.normalize_published_date(value), expected)

    def test_bad_dates_are_not_replaced_with_today(self):
        for value in [None, "", "Date not available", "invalid", {}, True, 1e100]:
            with self.subTest(value=value):
                self.assertIsNone(news.normalize_published_date(value))

    def test_ist_day_boundary_and_future_filter(self):
        settings = CONFIG["rss"]
        boundary = article(published_at=datetime(2026, 10, 7))
        self.assertTrue(news._recent(boundary, settings, NOW))
        for date in [datetime(2026, 10, 6, 23, 59), datetime(2026, 10, 9, 12, 1), None]:
            self.assertFalse(news._recent(article(published_at=date), settings, NOW))
        self.assertEqual(news.normalize_published_date("2026-10-06T18:30:00Z"), boundary["published_at"])

    def test_tracking_fragments_scheme_and_query_order_deduplicate(self):
        first = "HTTP://WWW.Example.com:80/story/?b=2&utm_source=hn&a=1&fbclid=x#comments"
        self.assertEqual(news.normalize_url(first), news.normalize_url("https://example.com/story?a=1&b=2"))
        self.assertNotEqual(news.normalize_url("https://example.com/?id=1"),
                            news.normalize_url("https://example.com/?id=2"))
        self.assertNotEqual(news.normalize_url("https://example.com/Story"),
                            news.normalize_url("https://example.com/story"))

    def test_arxiv_abstract_pdf_and_revision_aliases(self):
        urls = ["http://arxiv.org/abs/2610.00001v1", "https://arxiv.org/pdf/2610.00001v2.pdf",
                "https://export.arxiv.org/abs/2610.00001"]
        self.assertEqual(len({news.normalize_url(url) for url in urls}), 1)

    def test_invalid_links(self):
        for url in [None, "", "/relative", "javascript:alert(1)", "https://host:bad/x", "https://[broken"]:
            self.assertEqual(news.normalize_url(url), "")

    def test_duplicate_url_title_aliases_and_original_link(self):
        original = article(link="https://example.com/story?utm_source=rss#top")
        duplicate = article(2, link="http://www.example.com/story/")
        alias = article(3, title=duplicate["title"].upper())
        different = article(4)
        result = news.deduplicate_articles([original, duplicate, alias, different])
        self.assertEqual(result, [original, different])
        self.assertEqual(result[0]["link"], "https://example.com/story?utm_source=rss#top")


class RSSTests(OfflineTest):
    def test_scans_past_two_entries_and_filters_dates_before_cap(self):
        self.enterContext(patch.object(news, "feed_links", {"https://feed.test": "Feed"}))
        self.config["rss"]["max_articles_per_feed"] = 2
        self.routes["https://feed.test"] = rss([
            rss_item(1, pubDate=OLD), rss_item(2, pubDate=""), rss_item(3), rss_item(4), rss_item(5),
        ])
        articles = self.collect("rss")
        self.assertEqual([item["title"] for item in articles], ["Python story 3", "Python story 4"])
        self.assert_shape(articles[0])
        self.assertEqual(articles[0]["category"], "Programming")
        self.assertEqual(articles[0]["description"], "Technical & useful details.")

    def test_atom_updated_date_and_content_fallback(self):
        self.enterContext(patch.object(news, "feed_links", {"https://feed.test": "Atom"}))
        self.routes["https://feed.test"] = b"""<feed xmlns='http://www.w3.org/2005/Atom'>
        <entry><title>Rust release</title><updated>2026-10-09T05:00:00Z</updated>
        <content type='html'>&lt;p&gt;Compiler improvements&lt;/p&gt;</content>
        <link href='https://example.com/rust'/></entry></feed>"""
        articles = self.collect("rss")
        self.assertEqual(articles[0]["description"], "Compiler improvements")
        self.assertEqual(articles[0]["published_at"], datetime(2026, 10, 9, 10, 30))
        self.assertIsNone(articles[0]["category"])

    def test_duplicate_entries_do_not_consume_feed_limit(self):
        self.enterContext(patch.object(news, "feed_links", {"https://feed.test": "Feed"}))
        self.config["rss"]["max_articles_per_feed"] = 2
        self.routes["https://feed.test"] = rss([rss_item(1), rss_item(1), rss_item(2)])
        self.assertEqual(len(self.collect("rss")), 2)

    def test_relative_rss_link_is_resolved_against_feed_url(self):
        self.enterContext(patch.object(news, "feed_links", {"https://feed.test/rss.xml": "Feed"}))
        self.routes["https://feed.test/rss.xml"] = rss([rss_item(link="/articles/python?utm_source=rss")])
        articles = self.collect("rss")
        self.assertEqual(articles[0]["link"], "https://feed.test/articles/python?utm_source=rss")

    def test_recoverable_malformed_xml_is_reported_and_valid_entries_survive(self):
        self.enterContext(patch.object(news, "feed_links", {"https://feed.test": "Feed"}))
        self.routes["https://feed.test"] = rss([rss_item()]).replace(b"</channel>", b"")
        with self.assertLogs(news.LOGGER, level="WARNING") as logs:
            self.assertEqual(len(self.collect("rss")), 1)
        self.assertIn("malformed feed", " ".join(logs.output))

    def test_timeout_and_non_feed_do_not_block_other_feeds(self):
        self.enterContext(patch.object(news, "feed_links", {
            "https://slow.test": "Slow", "https://html.test": "HTML", "https://feed.test": "Good"}))
        self.routes.update({"https://slow.test": requests.Timeout("slow"),
                            "https://html.test": b"<html>Not a feed</html>",
                            "https://feed.test": rss([rss_item()])})
        with self.assertLogs(news.LOGGER, level="WARNING") as logs:
            articles = self.collect("rss")
        self.assertEqual(len(articles), 1)
        self.assertIn("Slow", " ".join(logs.output))
        self.assertIn("HTML", " ".join(logs.output))

    def test_source_deadline_keeps_already_fetched_feeds(self):
        self.enterContext(patch.object(news, "feed_links", {"https://good.test": "Good", "https://slow.test": "Slow"}))
        self.routes.update({"https://good.test": rss([rss_item()]),
                            "https://slow.test": news.SourceTimeout("budget exhausted")})
        with self.assertLogs(news.LOGGER, level="WARNING"):
            self.assertEqual(len(self.collect("rss")), 1)

    def test_feed_diversity_before_total_rss_cap(self):
        self.enterContext(patch.object(news, "feed_links", {"https://one.test": "One", "https://two.test": "Two"}))
        self.config["rss"]["max_articles"] = 2
        self.routes.update({"https://one.test": rss([rss_item(1), rss_item(2)]),
                            "https://two.test": rss([rss_item(3)])})
        self.assertEqual([item["source"] for item in self.collect("rss")], ["One", "Two"])


class MediumTests(OfflineTest):
    def test_normal_and_medium_feed_configs_are_separate(self):
        normal = json.loads((news.CONFIG_PATH.parent / "feeds.json").read_text(encoding="utf-8"))
        medium = json.loads((news.CONFIG_PATH.parent / "medium_feeds.json").read_text(encoding="utf-8"))
        self.assertTrue(normal)
        self.assertTrue(medium)
        self.assertFalse(set(normal).intersection(medium))
        self.assertNotIn("Medium", normal.values())
        self.assertEqual(set(medium.values()), {"Medium"})

    def test_medium_uses_its_own_feeds_and_returns_same_article_shape(self):
        self.enterContext(patch.object(news, "feed_links", {"https://normal.test": "Normal"}))
        self.enterContext(patch.object(news, "medium_feed_links", {"https://medium.test/ai": "Medium"}))
        self.routes["https://medium.test/ai"] = rss([rss_item()])
        articles = self.collect("medium")
        self.assertEqual(len(articles), 1)
        self.assert_shape(articles[0])
        self.assertEqual(articles[0]["source"], "Medium")
        self.assertEqual(self.get.call_args.args[0], "https://medium.test/ai")
        self.assertEqual(self.get.call_count, 1)

    def test_medium_topic_duplicates_do_not_consume_candidate_limit(self):
        self.enterContext(patch.object(news, "medium_feed_links", {
            "https://medium.test/ai": "Medium", "https://medium.test/ml": "Medium"}))
        self.config["medium"]["max_articles"] = 2
        self.routes.update({"https://medium.test/ai": rss([rss_item(1)]),
                            "https://medium.test/ml": rss([rss_item(1), rss_item(2)])})
        self.assertEqual([item["title"] for item in self.collect("medium")],
                         ["Python story 1", "Python story 2"])

    def test_medium_timeout_does_not_stop_normal_rss(self):
        self.enterContext(patch.object(news, "feed_links", {"https://normal.test": "Normal"}))
        self.enterContext(patch.object(news, "medium_feed_links", {"https://medium.test": "Medium"}))
        self.routes.update({"https://medium.test": news.SourceTimeout("Medium budget exhausted"),
                            "https://normal.test": rss([rss_item()])})
        with self.assertLogs(news.LOGGER, level="WARNING"):
            self.assertEqual(self.collect("medium"), [])
        self.assertEqual(len(self.collect("rss")), 1)


class HackerNewsTests(OfflineTest):
    def test_shape_score_relevance_type_and_date_filters(self):
        self.add_hn([hn_item(1, score=1), hn_item(2, deleted=True), hn_item(3, dead=True),
                     hn_item(4, type="job"), hn_item(5, url=""), hn_item(6, title="Holiday recipes"),
                     hn_item(7, time=0), hn_item(8, time=None), hn_item(9, time=9999999999),
                     None, hn_item(11)])
        articles = self.collect("hacker_news")
        self.assertEqual(len(articles), 1)
        self.assert_shape(articles[0])
        self.assertEqual(articles[0]["link"], "https://example.com/hn/11")
        self.assertIn("Publisher abstract unavailable", articles[0]["description"])
        self.assertIsNone(articles[0]["category"])

    def test_keyword_boundaries(self):
        self.assertFalse(news._matches_keywords("A said sail", ["AI"]))
        self.assertTrue(news._matches_keywords("New AI-based compiler", ["AI"]))
        self.assertTrue(news._matches_keywords("anything", []))

    def test_item_failures_and_limits(self):
        self.add_hn([requests.Timeout("item timeout"), hn_item(2), hn_item(3), hn_item(4)])
        self.config["hacker_news"].update(max_articles=1, max_items_to_check=3)
        with self.assertLogs(news.LOGGER, level="WARNING"):
            articles = self.collect("hacker_news")
        self.assertEqual(len(articles), 1)
        self.assertEqual(self.get.call_count, 3)  # List + failed item + accepted item.

    def test_later_source_timeout_keeps_accepted_items(self):
        self.add_hn([hn_item(), news.SourceTimeout("budget exhausted")])
        with self.assertLogs(news.LOGGER, level="WARNING") as logs:
            self.assertEqual(len(self.collect("hacker_news")), 1)
        self.assertIn("retaining 1 articles", " ".join(logs.output))

    def test_scan_limit_is_enforced_even_when_no_item_qualifies(self):
        self.add_hn([hn_item(1, score=0), hn_item(2)])
        self.config["hacker_news"]["max_items_to_check"] = 1
        self.assertEqual(self.collect("hacker_news"), [])
        self.assertEqual(self.get.call_count, 2)


class GitHubTests(OfflineTest):
    def setUp(self):
        super().setUp()
        self.config["github"]["projects"] = ["owner/project"]
        self.url = "https://api.github.com/repos/owner/project/releases"

    def test_only_recent_stable_releases_with_correct_dates_and_shape(self):
        self.config["github"]["releases_per_project"] = 10
        self.routes[self.url] = [release(1, draft=True), release(2, prerelease=True),
                                release(3, published_at=OLD), release(4, published_at=None),
                                release(5, published_at="2026-10-08T05:00:00Z"), release(6)]
        articles = self.collect("github")
        self.assertEqual(len(articles), 1)
        self.assert_shape(articles[0])
        self.assertEqual(articles[0]["title"], "owner/project: v1.6")
        self.assertEqual(articles[0]["link"], release(6)["html_url"])
        self.assertEqual(articles[0]["published_at"], datetime(2026, 10, 9, 10, 30))
        self.assertEqual(articles[0]["category"], "Open Source")
        self.assertNotIn("Authorization", self.get.call_args.kwargs["headers"])

    def test_project_failure_continues_and_tag_name_fallback(self):
        self.config["github"]["projects"] = ["missing/project", "owner/project"]
        self.routes["https://api.github.com/repos/missing/project/releases"] = response({}, 404)
        self.routes[self.url] = [release(name=None, body=None)]
        with self.assertLogs(news.LOGGER, level="WARNING"):
            articles = self.collect("github")
        self.assertEqual(articles[0]["title"], "owner/project: v1.1")
        self.assertIn("release notes unavailable", articles[0]["description"])

    def test_rate_limit_keeps_partial_results_and_stops_requests(self):
        self.config["github"]["projects"] = ["owner/project", "limited/project", "unrequested/project"]
        self.routes[self.url] = [release()]
        self.routes["https://api.github.com/repos/limited/project/releases"] = response({}, 403)
        with self.assertLogs(news.LOGGER, level="WARNING") as logs:
            self.assertEqual(len(self.collect("github")), 1)
        self.assertEqual(self.get.call_count, 2)
        self.assertIn("rate limit", " ".join(logs.output))

    def test_total_release_limit_and_description_bound(self):
        self.config["github"].update(max_articles_per_project=3, max_articles=2)
        self.routes[self.url] = [release(i, body="x" * 8000) for i in range(3)]
        articles = self.collect("github")
        self.assertEqual(len(articles), 2)
        self.assertTrue(all(len(item["description"]) == 6000 for item in articles))


class ArxivTests(OfflineTest):
    def test_category_keywords_dates_limits_and_shape(self):
        self.config["arxiv"]["max_articles"] = 1
        self.routes[news.ARXIV_API] = atom([
            paper(1, category="physics.optics"), paper(2, title="Classical geometry", summary="A theorem"),
            paper(3, published=OLD, updated=RECENT), paper(4, published=""), paper(5), paper(6),
        ])
        articles = self.collect("arxiv")
        self.assertEqual(len(articles), 1)
        self.assert_shape(articles[0])
        self.assertEqual(articles[0]["link"], paper(5)["id"])
        self.assertEqual(articles[0]["description"], paper(5)["summary"])
        params = self.get.call_args.kwargs["params"]
        self.assertEqual(params["sortBy"], "submittedDate")
        self.assertIn("cat:cs.AI OR cat:cs.LG OR cat:cs.CL", params["search_query"])
        self.assertIn("202610061830 TO 202610090630", params["search_query"])
        self.assertEqual(self.get.call_count, 1)

    def test_http_200_api_error_is_reported(self):
        self.routes[news.ARXIV_API] = atom([paper(id="http://arxiv.org/api/errors#bad_query", summary="Invalid query")])
        with self.assertLogs(news.LOGGER, level="WARNING") as logs:
            self.assertEqual(self.collect("arxiv"), [])
        self.assertIn("Invalid query", " ".join(logs.output))

    def test_empty_result_and_disabled_source(self):
        self.routes[news.ARXIV_API] = atom([])
        self.assertEqual(self.collect("arxiv"), [])
        self.config["arxiv"]["enabled"] = False
        self.get.reset_mock()
        self.assertEqual(self.collect("arxiv"), [])
        self.get.assert_not_called()


class NetworkAndIntegrationTests(OfflineTest):
    def test_explicit_timeouts_and_response_size_limit(self):
        self.config["rss"]["max_response_bytes"] = 3
        self.routes["https://large.test"] = b"1234"
        with requests.Session() as session:
            client = news.SourceClient(session, self.config["rss"], self.config["network"])
            with self.assertRaisesRegex(ValueError, "size limit"):
                client.get("https://large.test")
        self.assertEqual(self.get.call_args.kwargs["timeout"], (3, 8))
        self.assertTrue(self.get.call_args.kwargs["stream"])

    def test_larger_rss_limit_does_not_increase_api_limit(self):
        self.config["network"]["max_response_bytes"] = 3
        self.config["rss"]["max_response_bytes"] = 10
        self.routes["https://feed.test"] = b"1234"
        with requests.Session() as session:
            rss_client = news.SourceClient(session, self.config["rss"], self.config["network"])
            api_client = news.SourceClient(session, self.config["arxiv"], self.config["network"])
            self.assertEqual(rss_client.get("https://feed.test"), b"1234")
            with self.assertRaisesRegex(ValueError, "3 bytes"):
                api_client.get("https://feed.test")

    def test_expired_source_budget_stops_before_request(self):
        with requests.Session() as session:
            with patch.object(news, "monotonic", side_effect=[0, 200]):
                client = news.SourceClient(session, self.config["rss"], self.config["network"])
                with self.assertRaises(news.SourceTimeout):
                    client.get("https://unrequested.test")
        self.get.assert_not_called()

    def test_slow_stream_is_stopped(self):
        self.routes["https://slow.test"] = b"content"
        with requests.Session() as session:
            with patch.object(news, "monotonic", side_effect=[0, 0, 0, 16, 16]):
                client = news.SourceClient(session, self.config["rss"], self.config["network"])
                with self.assertRaisesRegex(requests.Timeout, "request time budget"):
                    client.get("https://slow.test")

    def test_malformed_json_and_wrong_shape_are_isolated(self):
        for payload in [b"{broken", {"unexpected": "shape"}]:
            self.routes[f"{news.HN_API}/topstories.json"] = payload
            with self.assertLogs(news.LOGGER, level="WARNING"):
                self.assertEqual(self.collect("hacker_news"), [])

    def test_full_fetch_cross_source_dedup_and_cleaning_compatibility(self):
        self.enterContext(patch.object(news, "feed_links", {"https://feed.test": "Feed"}))
        self.enterContext(patch.object(news, "medium_feed_links", {"https://medium.test": "Medium"}))
        self.enterContext(patch.object(news, "datetime", wraps=datetime)).now.return_value = NOW
        self.routes["https://feed.test"] = rss([rss_item(1, link="https://example.com/shared?utm_source=rss")])
        self.routes["https://medium.test"] = rss([rss_item(900)])
        self.add_hn([hn_item(1, title="Python alternate headline", url="http://www.example.com/shared/"), hn_item(2)])
        for project in CONFIG["github"]["projects"]:
            self.routes[f"https://api.github.com/repos/{project}/releases"] = [release(
                html_url=f"https://github.com/{project}/releases/tag/v1.0")]
        self.routes[news.ARXIV_API] = atom([paper()])
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            articles = news.fetch_news()
        self.assertEqual(len(articles), 10)  # RSS + six projects + arXiv + unique HN + Medium.
        self.assertIn("Shortlist mix (rss: 1, github: 6, arxiv: 1, hacker_news: 1, medium: 1)", output.getvalue())
        for item in articles:
            self.assert_shape(item)
        self.assertIn("https://example.com/shared?utm_source=rss", [item["link"] for item in articles])
        self.assertNotIn("Python alternate headline", [item["title"] for item in articles])
        from data_cleaning import clean_articles
        with patch("data_cleaning.datetime", wraps=datetime) as clock:
            clock.now.return_value = NOW
            cleaned = clean_articles(articles)
        self.assertEqual(len(cleaned), len(articles))
        self.assertTrue(all(set(item) == FIELDS for item in cleaned))

    def test_failed_source_does_not_block_healthy_sources(self):
        self.enterContext(patch.object(news, "feed_links", {"https://feed.test": "Feed"}))
        self.enterContext(patch.object(news, "datetime", wraps=datetime)).now.return_value = NOW
        self.routes["https://feed.test"] = rss([rss_item()])
        self.routes[f"{news.HN_API}/topstories.json"] = requests.Timeout("HN is slow")
        self.routes[news.ARXIV_API] = response({}, 503)
        for project in CONFIG["github"]["projects"]:
            self.routes[f"https://api.github.com/repos/{project}/releases"] = []
        with self.assertLogs(news.LOGGER, level="WARNING") as logs:
            articles = news.fetch_news()
        self.assertEqual(len(articles), 1)
        self.assertIn("HN is slow", " ".join(logs.output))
        self.assertIn("503", " ".join(logs.output))

    def test_shortlist_balances_sources_even_with_many_more_rss_candidates(self):
        groups = [[article(i, source=f"Publisher {i // 4}") for i in range(80)],
                  [article(100 + i, "GitHub Releases") for i in range(20)],
                  [article(200 + i, "arXiv") for i in range(20)],
                  [article(300 + i, "Hacker News") for i in range(20)]]
        selected, _ = news.select_articles(groups, CONFIG["selection"])
        self.assertEqual(len(selected), 48)
        counts = Counter(item["source"] for item in selected)
        self.assertEqual(counts["Hacker News"], 12)
        self.assertEqual(counts["arXiv"], 12)
        self.assertEqual(counts["GitHub Releases"], 12)
        self.assertEqual(sum(count for name, count in counts.items() if name.startswith("Publisher")), 12)
        self.assertTrue(all(count <= 3 for name, count in counts.items() if name.startswith("Publisher")))

    def test_rss_does_not_take_unused_api_slots(self):
        groups = [[article(i, source=f"Publisher {i // 4}") for i in range(80)],
                  [article(100 + i, "GitHub Releases") for i in range(2)],
                  [article(200 + i, "arXiv") for i in range(4)],
                  [article(300 + i, "Hacker News") for i in range(7)]]
        selected, _ = news.select_articles(groups, CONFIG["selection"])
        self.assertEqual(len(selected), 25)
        self.assertEqual(sum(item["source"].startswith("Publisher") for item in selected), 12)

    def test_medium_has_reserved_slots_without_reducing_normal_rss(self):
        groups = [[article(i, source=f"Publisher {i // 4}") for i in range(80)],
                  [article(100 + i, "GitHub Releases") for i in range(20)],
                  [article(200 + i, "arXiv") for i in range(20)],
                  [article(300 + i, "Hacker News") for i in range(20)],
                  [article(400 + i, "Medium") for i in range(100)]]
        selected, _ = news.select_articles(groups, CONFIG["selection"])
        counts = Counter(item["source"] for item in selected)
        self.assertEqual(len(selected), 60)
        self.assertEqual(counts["Medium"], 12)
        self.assertEqual(sum(count for name, count in counts.items() if name.startswith("Publisher")), 12)
        self.assertEqual(counts["Hacker News"], 12)
        self.assertEqual(counts["arXiv"], 12)
        self.assertEqual(counts["GitHub Releases"], 12)

    def test_current_candidate_caps_can_exceed_old_fifty_article_ceiling(self):
        groups = [[article(i, source=f"Publisher {i}") for i in range(20)],
                  [article(100 + i, "GitHub Releases") for i in range(CONFIG["github"]["max_articles"])],
                  [article(200 + i, "arXiv") for i in range(20)],
                  [article(300 + i, "Hacker News") for i in range(20)],
                  [article(400 + i, "Medium") for i in range(20)]]
        selected, _ = news.select_articles(groups, CONFIG["selection"])
        self.assertEqual(len(selected), 54)

    def test_cross_source_medium_duplicates_are_removed_before_filling_slots(self):
        normal = article(1)
        hn = article(2, "Hacker News")
        duplicate_rss = article(3, "Medium", link=normal["link"] + "?utm_source=medium")
        duplicate_hn = article(4, "Medium", title=hn["title"])
        medium = article(5, "Medium")
        selected, _ = news.select_articles(
            [[normal], [], [], [hn], [duplicate_rss, duplicate_hn, medium]], CONFIG["selection"])
        self.assertEqual(selected, [normal, hn, medium])

    def test_medium_cannot_take_unused_normal_rss_slots(self):
        groups = [[], [], [], [], [article(i, "Medium") for i in range(40)]]
        selected, _ = news.select_articles(groups, CONFIG["selection"])
        self.assertEqual(len(selected), 12)

    def test_rss_cap_applies_when_all_other_sources_fail(self):
        rss = [article(i, source=f"Publisher {i}") for i in range(40)]
        selected, _ = news.select_articles([rss, [], [], []], CONFIG["selection"])
        self.assertEqual(len(selected), 12)

    def test_unselected_rss_duplicate_does_not_suppress_api_article(self):
        settings = {**CONFIG["selection"], "max_articles_per_source": 1}
        first, overflow = article(1), article(2)
        hn = article(3, "Hacker News", link=overflow["link"])
        selected, _ = news.select_articles([[first, overflow], [], [], [hn]], settings)
        self.assertEqual(selected, [first, hn])

    def test_selected_duplicate_does_not_consume_another_source_slot(self):
        settings = {**CONFIG["selection"], "max_articles_per_source": 2}
        first, second = article(1), article(2)
        duplicate = article(3, "Hacker News", link=first["link"] + "?utm_source=hn")
        hn = [article(4, "Hacker News"), article(5, "Hacker News")]
        selected, _ = news.select_articles([[first, second], [], [], [duplicate, *hn]], settings)
        self.assertEqual(selected, [first, hn[0], second, hn[1]])

    def test_global_review_ceiling_still_applies(self):
        settings = {**CONFIG["selection"], "max_articles": 5}
        groups = [[article(i * 100 + j, f"Group {i}") for j in range(5)] for i in range(4)]
        selected, _ = news.select_articles(groups, settings)
        self.assertEqual(len(selected), 5)
        self.assertEqual(len({item["source"] for item in selected}), 4)

    def test_zero_source_cap_returns_without_selecting_articles(self):
        settings = {**CONFIG["selection"], "max_articles_per_source": 0}
        selected, _ = news.select_articles([[article()], [], [], []], settings)
        self.assertEqual(selected, [])

    def test_shortlist_prefers_recent_useful_descriptions_and_does_not_pad(self):
        older = article(1, published_at=datetime(2026, 10, 8))
        thin = article(2, description="Tiny snippet", published_at=datetime(2026, 10, 9, 11))
        rich = article(3)
        selected, _ = news.select_articles([[older, thin, rich], [], [], []], CONFIG["selection"])
        self.assertEqual(selected, [rich, thin, older])


class PreviewTests(unittest.TestCase):
    def test_preview_prints_articles_without_running_processing(self):
        items = [article()]
        with patch.object(news, "fetch_news", return_value=items) as fetch, \
                patch.object(news, "fetch_sum_save") as process, \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            news.main(["--preview"])
        fetch.assert_called_once_with()
        process.assert_not_called()
        preview = json.loads(output.getvalue().split("\n", 1)[1])
        self.assertEqual(set(preview[0]), FIELDS)
        self.assertEqual(preview[0]["link"], items[0]["link"])
        self.assertEqual(preview[0]["published_at"], str(items[0]["published_at"]))

    def test_original_command_still_uses_existing_entry_point(self):
        with patch.object(news, "fetch_sum_save") as process, \
                patch.object(news, "fetch_news") as fetch:
            news.main([])
        process.assert_called_once_with()
        fetch.assert_not_called()


class SheetLimitTest(unittest.TestCase):
    def test_export_query_uses_configurable_review_ceiling(self):
        # Mock both database and sheet boundaries; no credentials or network are used.
        import google_sheets
        connection, sheet = Mock(), Mock()
        cursor = connection.cursor.return_value
        cursor.fetchall.return_value = [{"id": 1, "title": "A release", "source": "GitHub",
            "description": "Details", "published_at": datetime(2026, 10, 9),
            "url": "https://example.com/release", "summary": "Summary", "category": "Open Source"}]
        with patch.object(google_sheets, "get_connection", return_value=connection), \
                patch.object(google_sheets, "get_sheet", return_value=sheet), \
                patch.object(google_sheets.Path, "read_text", return_value=json.dumps({
                    "selection": {"max_articles": 37}})):
            google_sheets.export_articles_to_sheet()
        query, params = cursor.execute.call_args.args
        self.assertIn("LIMIT %s", query)
        self.assertEqual(params[1], 37)
        self.assertIn("TRIM(summary) <> ''", query)
        data = sheet.update.call_args.args[0]
        self.assertEqual(data[0][-1], "Mark")
        self.assertEqual(data[1][6], "https://example.com/release")


if __name__ == "__main__":
    unittest.main()
