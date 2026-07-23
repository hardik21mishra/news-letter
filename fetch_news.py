import feedparser

feed_links = [
    "https://www.theguardian.com/world/rss", 
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://abcnews.go.com/abcnews/topstories"
]

def fetch_news():
    articles = []

    for feed_url in feed_links:
        feed = feedparser.parse(feed_url)
        # print(feed)

        for entry in feed.entries[:5]:
            article = {
                "title": entry.get("title", "nahi mila Title"),
                "description": entry.get("summary", "nahi mila Description"),
                "published_date": entry.get("published", "nahi mili date"),
                "link": entry.get("link", ""),
                "category": None,
                "summary": None
            }
            # print(article["title"])
            # print("\n")

            articles.append(article)
    return articles

# fetch_news()