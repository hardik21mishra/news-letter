import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
ARTICLE_AGE_DAYS = 2   # only news articles which published in last 2 days are considered

def clean_articles(articles):
    original_count = len(articles)

    articles_df = pd.DataFrame(articles).copy()

    if "published_at" not in articles_df:
        articles_df["published_at"] = pd.NaT
    if "title" not in articles_df:
        articles_df["title"] = None

    articles_df["parsed_published_at"] = pd.to_datetime(
        articles_df["published_at"], errors="coerce"
    )

    dated_articles = articles_df[articles_df["parsed_published_at"].notna()].copy()
    missing_date_count = original_count - len(dated_articles)
    print(f"Articles without published_at: {missing_date_count}")

    cutoff_date = datetime.now(IST).date() - timedelta(days=ARTICLE_AGE_DAYS)
    recent_articles = dated_articles[
        dated_articles["parsed_published_at"].dt.date >= cutoff_date
    ].copy()

    old_article_count = len(dated_articles) - len(recent_articles)
    print(f"Articles older than {ARTICLE_AGE_DAYS} days: {old_article_count}")

    recent_articles = recent_articles.sort_values(
        by="parsed_published_at", ascending=False
    )

    cleaned_articles_df = recent_articles.drop_duplicates(
        subset="title", keep="first"
    ).drop(columns="parsed_published_at")
    
    cleaned_articles = cleaned_articles_df.to_dict("records")

    duplicate_count = len(recent_articles) - len(cleaned_articles)
    print(f"Duplicate-title articles: {duplicate_count}")
    print("\nArticle cleaning completed.")
    print(f"Articles before cleaning : {original_count}")
    print(f"Articles removed         : {original_count - len(cleaned_articles)}")
    print(f"Articles remaining       : {len(cleaned_articles)}")
    return cleaned_articles

if __name__ == "__main__":
    print("nothing, preferebly run it from the fetch_articles.py")