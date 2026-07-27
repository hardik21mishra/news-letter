import feedparser

feed_links = {
    "https://www.theguardian.com/world/rss" : "The Guardian", 
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml" : "New York Times",
    "https://feeds.bbci.co.uk/news/rss.xml" : "BBC",
    "https://www.aljazeera.com/xml/rss/all.xml" : "Al Jazeera",
    "https://abcnews.go.com/abcnews/topstories" : "ABC News"
}

def fetch_news():
    articles = []
        #   (x,y)
    for feed_url, source in feed_links.items():
        feed = feedparser.parse(feed_url)
        # print(feed)

        for entry in feed.entries[:5]:
            article = {
                "title": entry.get("title", "nahi mila Title"),
                "source": source,
                "description": entry.get("summary", "nahi mila Description"),
                "published_date": entry.get("published", "nahi mili date"),
                "link": entry.get("link", ""),
                "category": None,
                "summary": None
            }
            # print(article)
            # print(article["title"])
            # print("\n")

            articles.append(article)
    return articles

fetch_news()