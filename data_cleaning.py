import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from db import get_connection

IST = ZoneInfo("Asia/Kolkata")

def clean_articles():
    conn = get_connection()

    # Read all articles from the database
    df = pd.read_sql("""
        SELECT id, title, published_at
        FROM articles
    """, conn)

    if df.empty:
        print("No articles found in the database.")
        conn.close()
        return
    original_count = len(df)

#   Remove articles without a published_at date
    df["published_at"] = pd.to_datetime(
        df["published_at"],
        errors="coerce"
    )

    missing_date = df["published_at"].isna()
    missing_date_ids = df.loc[missing_date, "id"].tolist()
    df = df[~missing_date].copy()
    print(f"Articles without published_at: {len(missing_date_ids)}")


    # Remove articles older than 3 days
    now_ist = datetime.now(IST)

    # MySQL DATETIME does not contain timezone information,
    # so convert the current IST time to a naive datetime.
    now_ist_naive = now_ist.replace(tzinfo=None)
    cutoff = now_ist_naive - timedelta(days=3)
    old_articles = df["published_at"] < cutoff
    old_article_ids = df.loc[old_articles, "id"].tolist()
    df = df[~old_articles].copy()

    print(f"Articles older than 3 days: {len(old_article_ids)}")

    # Remove duplicate titles and Sort newest articles first
    df = df.sort_values(
        by="published_at",
        ascending=False
    )
    duplicate_titles = df.duplicated(
        subset=["title"],
        keep="first"
    )
    duplicate_ids = df.loc[duplicate_titles, "id"].tolist()
    df = df[~duplicate_titles].copy()
    print(f"Duplicate-title articles: {len(duplicate_ids)}")

    # Delete unwanted articles from Database

    ids_to_delete = (
        missing_date_ids
        + old_article_ids
        + duplicate_ids
    )
    # Remove duplicate IDs if an article matched
    ids_to_delete = list(set(ids_to_delete))

    if ids_to_delete:
        cur = conn.cursor()
        placeholders = ", ".join(["%s"] * len(ids_to_delete))
        cur.execute(
            f"""
            DELETE FROM articles
            WHERE id IN ({placeholders})
            """,
            tuple(ids_to_delete)
        )
        conn.commit()
        cur.close()
    conn.close()

    final_count = original_count - len(ids_to_delete)

    print("\nArticle cleaning completed.")
    print(f"Articles before cleaning : {original_count}")
    print(f"Articles deleted         : {len(ids_to_delete)}")
    print(f"Articles remaining       : {final_count}")

if __name__ == "__main__":
    clean_articles()