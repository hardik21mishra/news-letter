import json
from pathlib import Path
import feedparser
from bs4 import BeautifulSoup
import re
import html
from datetime import timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime

# Keep feed URLs and source labels in config/feeds.json, in fetching order.
feed_links = json.loads(
    (Path(__file__).resolve().parent / "config" / "feeds.json").read_text(encoding="utf-8")
)

IST = ZoneInfo("Asia/Kolkata")

def normalize_published_date(date_string):
    if date_string == "Date not available":
        return None
    
    if not date_string:
        return None
    try:
        dt = parsedate_to_datetime(date_string)

        # Convert RSS timezone -> IST
        dt = dt.astimezone(IST)
        # Remove timezone information because MySQL DATETIME
        # stores only date and time
        return dt.replace(tzinfo=None)
    except (TypeError, ValueError):
        return None

def clean_text(text):
    if not text:
        return "Description not found"

    text = html.unescape(text)
    text = BeautifulSoup(text, "html.parser").get_text(" ")
    text = re.sub(r'[\u200b-\u200d\uFEFF]', '', text)  # zero-width chars

    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")

    # strip all quote marks (straight + curly)
    text = re.sub(r'["“”‘’]', '', text)

    text = re.sub(r'\s+([.,!?;:])', r'\1', text)      # no space before punctuation
    text = re.sub(r'([.,!?;:])([A-Za-z])', r'\1 \2', text)  # space after punctuation
    text = re.sub(r'([.!?]){2,}', r'\1', text)         # remove repeated punctuation
    text = re.sub(r'\s+', ' ', text)                  #remove whitespace

    return text.strip()

def fetch_news():
    articles = []
    for feed_url, source in feed_links.items():
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:2]: #fetch only 2 articles(newest) from each source
            description = (
                entry.get("summary")
                or entry.get("description")
                or (
                    entry.get("content", [{}])[0].get("value", "") 
                    if entry.get("content") 
                    else ""
                )
            )
            rss_category = None

            if hasattr(entry, "tags") and entry.tags:
                rss_category = entry.tags[0].term
            elif entry.get("category"):
                rss_category = entry.get("category")

            article = {
                "title": clean_text(entry.get("title", "Title not found")),
                "source": source,
                "description": clean_text(description),
                "published_at": normalize_published_date(
                    entry.get("published")
                    or entry.get("updated")
                    or entry.get("pubDate")
                    or "Date not available"
                ),
                "link": entry.get("link", ""),
                "summary": None, 
                "category": rss_category
            }  
            articles.append(article)
            # print(article)
            # print("\n")
    return articles

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

if __name__ == "__main__":
    fetch_sum_save()
# fetch_news()