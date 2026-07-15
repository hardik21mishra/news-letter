from fetch_news import fetch_news
from categorize import process_news

def the_news():
    articles = fetch_news()
    articles = articles[:10]
    processed_articles = process_news(articles)
    return processed_articles

if __name__ == "__main__":
    processed_articles = the_news()
    for article in processed_articles:
        print("Title        :", article["title"])
        print("Category     :", article["category"])
        print("Summary      :", article["summary"])
        print("Published On :", article["published_date"])
        print("\n")