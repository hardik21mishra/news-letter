import feedparser

feed_links = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://techcrunch.com/feed/",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.feedburner.com/TheHackersNews"
]

def fetch_news():
    articles = []
    for feed_url in feed_links:

        feed = feedparser.parse(feed_url)
        # print(feed)

        for entry in feed.entries:
            article = {
                "title": entry.get("title", "nahi mila Title"),
                "description": entry.get("summary", "nahi mila Description"),
                "published_date": entry.get("published", "nahi mili date"),
                "category": None,
                "summary": None
            }
            # print(article["title"])
            articles.append(article)
    return articles

# fetch_news()