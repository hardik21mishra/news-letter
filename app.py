from fetch_news import fetch_news
from categorize import process_news
import json 

def save_to_json(articles):
    with open("news.json", "w") as f:
        json.dump(articles, f, indent = 2)
    print("saved articles to news.json")

def the_news():
    articles = fetch_news()
    articles = articles[:10]
    processed_articles = process_news(articles)
    save_to_json(processed_articles)
    return processed_articles

if __name__ == "__main__":
    processed_articles = the_news()
    for article in processed_articles:
        print("Title        :", article["title"])
        print("Category     :", article["category"])
        print("Summary      :", article["summary"])
        print("Published On :", article["published_date"])
        print("\n")