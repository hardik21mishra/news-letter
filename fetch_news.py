import argparse
import json
import logging
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from itertools import zip_longest
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import feedparser
import requests
from bs4 import BeautifulSoup
import re
import html
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime

# Keep normal and Medium RSS feeds in separate configuration files and source pools.
feed_links = json.loads(
    (Path(__file__).resolve().parent / "config" / "feeds.json").read_text(encoding="utf-8")
)
medium_feed_links = json.loads(
    (Path(__file__).resolve().parent / "config" / "medium_feeds.json").read_text(encoding="utf-8")
)

IST = ZoneInfo("Asia/Kolkata")
LOGGER = logging.getLogger(__name__)
CONFIG_PATH = Path(__file__).resolve().parent / "config" / "sources.json"
HN_API = "https://hacker-news.firebaseio.com/v0"
ARXIV_API = "https://export.arxiv.org/api/query"

def normalize_published_date(date_string):
    """Convert RFC 2822, ISO 8601, or Unix seconds to the existing naive IST format."""
    if date_string is None or date_string == "Date not available":
        return None
    try:
        if isinstance(date_string, (int, float)) and not isinstance(date_string, bool):
            dt = datetime.fromtimestamp(date_string, timezone.utc)
        elif isinstance(date_string, str):
            try:
                dt = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
            except ValueError:
                dt = parsedate_to_datetime(date_string)
        else:
            return None
        # Missing timezones are interpreted consistently, regardless of host timezone.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).replace(tzinfo=None)
    except (AttributeError, TypeError, ValueError, OverflowError, OSError):
        return None

def clean_text(text):
    """Remove markup and normalize whitespace without rewriting technical prose."""
    if not text:
        return "Description not found"

    text = html.unescape(text)
    text = BeautifulSoup(text, "html.parser").get_text(" ")
    # A zero-width word separator must not join adjacent words. Preserve joiners
    # used in other languages/emoji, apostrophes, version numbers, URLs, and code.
    text = re.sub(r'[\u200b\uFEFF]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def normalize_url(url):
    """A comparison key only: never replace the newsletter's original link."""
    try:
        parts = urlsplit(url.strip())
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return ""
        host = parts.hostname.lower().removeprefix("www.")
        port = parts.port
        default_port = 80 if parts.scheme.lower() == "http" else 443
        if port and port != default_port:
            host += f":{port}"
        path = parts.path.rstrip("/")
        if host in {"arxiv.org", "export.arxiv.org"}:
            host = "arxiv.org"
            path = re.sub(r"^/pdf/", "/abs/", path)
            path = re.sub(r"(?:v\d+)?(?:\.pdf)?$", "", path)
        tracking = {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid"}
        query = sorted(
            (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in tracking
        )
        return urlunsplit(("https", host, path, urlencode(query), ""))
    except (AttributeError, TypeError, ValueError):
        return ""


def deduplicate_articles(articles):
    """Keep the first occurrence, by URL or exact whitespace/case-normalized title."""
    seen_urls, seen_titles, unique = set(), set(), []
    for article in articles:
        url = normalize_url(article["link"])
        title = " ".join(article["title"].casefold().split())
        duplicate = url in seen_urls or title in seen_titles
        # Remember aliases even when this occurrence is discarded.
        if url:
            seen_urls.add(url)
        if title:
            seen_titles.add(title)
        if not duplicate:
            unique.append(article)
    return unique


class SourceTimeout(requests.Timeout):
    """Stop one source while retaining the articles already fetched from it."""


class SourceClient:
    def __init__(self, session, settings, network):
        self.session = session
        self.network = network
        self.max_response_bytes = settings.get("max_response_bytes", network["max_response_bytes"])
        self.deadline = monotonic() + settings["time_budget_seconds"]

    def get(self, url, **kwargs):
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise SourceTimeout("source time budget exhausted")
        timeout = (
            min(self.network["connect_timeout_seconds"], remaining),
            min(self.network["read_timeout_seconds"], remaining),
        )
        request_deadline = min(
            self.deadline, monotonic() + self.network["request_timeout_seconds"]
        )
        # Stream with a size/deadline check so a trickling or huge feed is skipped.
        with self.session.get(url, timeout=timeout, stream=True, **kwargs) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_content(chunk_size=16384):
                if monotonic() > self.deadline:
                    raise SourceTimeout("source time budget exhausted")
                if monotonic() > request_deadline:
                    raise requests.Timeout("request time budget exhausted")
                body.extend(chunk)
                if len(body) > self.max_response_bytes:
                    raise ValueError(f"response exceeds configured size limit ({self.max_response_bytes} bytes)")
            return bytes(body)

    def json(self, url, **kwargs):
        return json.loads(self.get(url, **kwargs))


def _article(title, source, description, published_at, link, category=None):
    return {
        "title": clean_text(title) if title else "",
        "source": source,
        "description": clean_text(description),
        "published_at": normalize_published_date(published_at),
        "link": link,
        "summary": None,
        "category": category,
    }


def _recent(article, settings, now):
    # Match data_cleaning.py's calendar-day cutoff; do not invent missing dates.
    published = article["published_at"]
    return bool(
        article["title"] and normalize_url(article["link"]) and published
        and now.date() - timedelta(days=settings["max_age_days"]) <= published.date()
        and published <= now.replace(tzinfo=None)
    )


def _matches_keywords(text, keywords):
    # Word boundaries prevent "AI" matching "said", for example. [] disables this filter.
    return not keywords or any(
        re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text, re.IGNORECASE)
        for word in keywords
    )


def _parse_feed(body, label, base_url=""):
    # We pass downloaded XML bytes, not an HTTP response; declare the parser input
    # type and retain the feed base URL for relative article links.
    feed = feedparser.parse(body, response_headers={
        "content-location": base_url, "content-type": "application/xml",
    })
    if feed.get("bozo"):
        LOGGER.warning("%s: malformed feed: %s", label, feed.get("bozo_exception"))
    if not feed.get("version"):
        raise ValueError("response is not RSS/Atom")
    return feed.entries


def fetch_rss(client, settings, now, feeds=None):
    batches = []
    for feed_url, source in (feed_links if feeds is None else feeds).items():
        try:
            entries = _parse_feed(client.get(feed_url), source, feed_url)
            candidates = []
            for entry in entries[:settings["entries_per_feed"]]:
                description = entry.get("summary") or entry.get("description")
                if not description:
                    description = (entry.get("content") or [{}])[0].get("value", "")
                category = (entry.get("tags") or [{}])[0].get("term") or entry.get("category")
                article = _article(
                    entry.get("title"), source, description,
                    entry.get("published") or (entry["updated"] if "updated" in entry else None)
                    or entry.get("pubDate"),
                    entry.get("link", ""), category,
                )
                if _recent(article, settings, now):
                    candidates.append(article)
            candidates.sort(key=lambda article: article["published_at"], reverse=True)
            batches.append(deduplicate_articles(candidates)[:settings["max_articles_per_feed"]])
        except SourceTimeout as exc:
            LOGGER.warning("RSS stopped at %s; keeping earlier feeds: %s", source, exc)
            break
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            LOGGER.warning("RSS %s (%s) failed: %s", source, feed_url, exc)
    # Take one from each feed before taking a second, so early feeds cannot fill the cap.
    for row in zip_longest(*batches):
        yield from (article for article in row if article is not None)


def fetch_medium(client, settings, now):
    """Use the same RSS parser with Medium's own feeds, budget, and candidate cap."""
    yield from fetch_rss(client, settings, now, feeds=medium_feed_links)


def fetch_hacker_news(client, settings, now):
    ids = client.json(f"{HN_API}/topstories.json")
    if not isinstance(ids, list):
        raise ValueError("expected a Hacker News story ID list")
    for item_id in ids[:settings["max_items_to_check"]]:
        try:
            item = client.json(f"{HN_API}/item/{int(item_id)}.json")
            if not isinstance(item, dict) or item.get("type") != "story":
                continue
            if item.get("deleted") or item.get("dead") or item.get("score", 0) < settings["min_score"]:
                continue
            # Link posts only: jobs, polls, and text-only Ask HN threads add noise.
            if not normalize_url(item.get("url")):
                continue
            title = item.get("title", "")
            if not _matches_keywords(clean_text(title + " " + (item.get("text") or "")), settings["keywords"]):
                continue
            # HN normally has no publisher abstract. Do not pretend metadata is one.
            description = item.get("text") or (
                f"Community-discovered link: {title}. "
                f"Hacker News score: {item.get('score', 0)}; "
                f"comments: {item.get('descendants', 0)}. Publisher abstract unavailable."
            )
            yield _article(title, "Hacker News", description, item.get("time"), item["url"])
        except SourceTimeout:
            raise
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            LOGGER.warning("Hacker News item %s failed: %s", item_id, exc)


def fetch_github_releases(client, settings, now):
    for project in settings["projects"]:
        try:
            if not re.fullmatch(r"[\w.-]+/[\w.-]+", project):
                raise ValueError("project must use owner/repository format")
            releases = client.json(
                f"https://api.github.com/repos/{project}/releases",
                params={"per_page": min(settings["releases_per_project"], 100)},
                headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
            )
            if not isinstance(releases, list):
                raise ValueError("expected a GitHub releases list")
            candidates = []
            for release in releases[:settings["releases_per_project"]]:
                if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
                    continue
                name = release.get("name") or release.get("tag_name")
                if not name:
                    continue
                article = _article(
                    f"{project}: {name}", f"GitHub Releases ({project})",
                    release.get("body") or f"Stable release {name} of {project}; release notes unavailable.",
                    release.get("published_at"), release.get("html_url", ""), "Open Source",
                )
                if _recent(article, settings, now):
                    candidates.append(article)
            candidates.sort(key=lambda article: article["published_at"], reverse=True)
            yield from deduplicate_articles(candidates)[:settings["max_articles_per_project"]]
        except SourceTimeout:
            raise
        except requests.HTTPError as exc:
            LOGGER.warning("GitHub %s failed: %s", project, exc)
            if exc.response is not None and exc.response.status_code in {403, 429}:
                LOGGER.warning("GitHub access/rate limit reached; skipping remaining projects this run")
                return
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            LOGGER.warning("GitHub %s failed: %s", project, exc)


def fetch_arxiv(client, settings, now):
    if not settings["categories"]:
        return
    cutoff = datetime.combine(
        now.date() - timedelta(days=settings["max_age_days"]), time.min, tzinfo=IST
    ).astimezone(timezone.utc)
    categories = " OR ".join(f"cat:{category}" for category in settings["categories"])
    query = f"({categories}) AND submittedDate:[{cutoff:%Y%m%d%H%M} TO {now.astimezone(timezone.utc):%Y%m%d%H%M}]"
    # One small request per run, no pagination or automatic retries.
    entries = _parse_feed(client.get(ARXIV_API, params={
        "search_query": query, "start": 0, "max_results": settings["max_results"],
        "sortBy": "submittedDate", "sortOrder": "descending",
    }), "arXiv")
    for entry in entries[:settings["max_results"]]:
        if "/api/errors" in entry.get("id", ""):
            raise ValueError(f"arXiv API error: {entry.get('summary', entry.get('title'))}")
        categories = {tag.get("term") for tag in entry.get("tags", [])}
        if not categories.intersection(settings["categories"]):
            continue
        title, abstract = entry.get("title", ""), entry.get("summary", "")
        if not _matches_keywords(title + " " + abstract, settings["keywords"]):
            continue
        link = next((link["href"] for link in entry.get("links", [])
                     if link.get("rel") == "alternate" and link.get("type") == "text/html"), entry.get("id", ""))
        # Original submission date, not the date of a revision to an old paper.
        yield _article(title, "arXiv", abstract, entry.get("published"), link, "Research")


def _collect_source(name, fetcher, settings, network, now):
    articles = []
    if not settings["enabled"] or settings["max_articles"] <= 0:
        return articles
    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": "PersonalTechNewsletter/1.0"})
            client = SourceClient(session, settings, network)
            for article in fetcher(client, settings, now):
                if not _recent(article, settings, now):
                    continue
                article["description"] = article["description"][:network["max_description_chars"]]
                articles = deduplicate_articles([*articles, article])
                if len(articles) >= settings["max_articles"]:
                    break
    except Exception as exc:
        # Isolation boundary: one API/parser failure must not take down the newsletter.
        LOGGER.warning("%s failed; retaining %d articles: %s", name, len(articles), exc)
    LOGGER.info("%s: %d eligible articles", name, len(articles))
    return articles


def select_articles(groups, settings):
    """Balance RSS, GitHub, arXiv, HN, and Medium without transferring unused slots."""
    unique = deduplicate_articles(article for group in groups for article in group)
    pools = [deque(group) for group in groups]
    # Rank normal RSS within its own pool. Medium retains the per-feed round-robin
    # order to give its topic feeds a turn, using a separate source allowance.
    pools[0] = deque(sorted(pools[0], key=lambda article: (
        article["published_at"].date(), len(article["description"]) >= 160,
        article["published_at"],
    ), reverse=True))
    selected, publishers, source_counts = [], Counter(), Counter()
    seen_urls, seen_titles = set(), set()
    while any(pools) and len(selected) < settings["max_articles"]:
        for index, pool in enumerate(pools):
            if source_counts[index] >= settings["max_articles_per_source"]:
                pool.clear()
                continue
            while pool:
                article = pool.popleft()
                publisher = article["source"]
                if index == 0 and publishers[publisher] >= settings["max_rss_articles_per_publisher"]:
                    continue
                url = normalize_url(article["link"])
                title = " ".join(article["title"].casefold().split())
                if url in seen_urls or title in seen_titles:
                    continue
                # Deduplicate only against selected articles: an RSS candidate
                # outside its allocation must not suppress an eligible API story.
                seen_urls.add(url)
                seen_titles.add(title)
                selected.append(article)
                publishers[publisher] += 1
                source_counts[index] += 1
                break
            if len(selected) >= settings["max_articles"]:
                break
    return selected, len(unique)


def fetch_news():
    settings = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    now = datetime.now(IST)
    # Separate sessions/budgets let sources make progress independently. The fixed
    # order is also the round-robin order used during shortlist selection.
    sources = [("rss", fetch_rss), ("github", fetch_github_releases),
               ("arxiv", fetch_arxiv), ("hacker_news", fetch_hacker_news),
               ("medium", fetch_medium)]
    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = [executor.submit(_collect_source, name, fetcher, settings[name], settings["network"], now)
                   for name, fetcher in sources]
        groups = [future.result() for future in futures]
    selected, unique_count = select_articles(groups, settings["selection"])
    total = sum(map(len, groups))
    counts = ", ".join(f"{name}: {len(group)}" for (name, _), group in zip(sources, groups))
    print(f"Fetching candidates ({counts}); {total - unique_count} cross-source duplicate candidates found; "
          f"{len(selected)} articles shortlisted for cleaning and Groq")
    selected_ids = {id(article) for article in selected}
    selected_counts = ", ".join(
        f"{name}: {sum(id(article) in selected_ids for article in group)}"
        for (name, _), group in zip(sources, groups)
    )
    print(f"Shortlist mix ({selected_counts})")
    return selected

# main

def fetch_sum_save():
    from categorize import process_news
    from db import init_db, save_articles
    from data_cleaning import clean_articles

    init_db() 

    articles = fetch_news()
    print(f"Fetched {len(articles)} articles total")

    articles = clean_articles(articles)
    articles = process_news(articles)
    missing_summary_count = sum(
        not str(article.get("summary") or "").strip()
        for article in articles
    )
    print("Categorized and summarized articles")
    print(f"Articles without summary after categorization: {missing_summary_count}")
    save_articles(articles)
    print("saved articles to the database")

def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch tech newsletter articles.")
    parser.add_argument(
        "--preview", action="store_true",
        help="Fetch and print articles only; skip Groq, database, and Google Sheets.",
    )
    args = parser.parse_args(argv)
    if args.preview:
        print("Fetching articles for terminal preview...", flush=True)
        articles = fetch_news()
        print(json.dumps(articles, default=str, indent=2, ensure_ascii=False))
    else:
        fetch_sum_save()

if __name__ == "__main__":
    main()
