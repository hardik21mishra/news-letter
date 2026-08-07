# Env vars MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

import os
import mysql.connector
from datetime import datetime, timezone
import json

from dotenv import load_dotenv
load_dotenv()

CA_CERT_PATH = os.environ.get("MYSQL_SSL_CA")

def get_connection():
    connect_args = dict(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
    )
    if CA_CERT_PATH:
        connect_args["ssl_ca"] = CA_CERT_PATH
    return mysql.connector.connect(**connect_args)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title TEXT,
            author TEXT,
            url VARCHAR(768) UNIQUE,
            published_at TEXT,
            source TEXT,
            category TEXT,
            description TEXT,
            summary TEXT,
            fetched_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS selections (
            id INT AUTO_INCREMENT PRIMARY KEY,
            article_id INT,
            mark_type VARCHAR(50),
            week_of TEXT,
            created_at TEXT,
            FOREIGN KEY (article_id) REFERENCES articles(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255),
            email VARCHAR(255) UNIQUE NOT NULL,
            contact_no VARCHAR(20),
            interests TEXT,
            subscribed_at TEXT,
            active BOOLEAN DEFAULT TRUE
        )
    """)

    conn.commit()
    cur.close()
    conn.close()
    print(f"MySQL tables ready on {os.environ['MYSQL_HOST']}")

def save_articles(articles):
    """
    Accepts a list of article dicts in the normalized shape used across
    the project (title, author, url, published_at, source, category,
    description, summary). Duplicate URLs are silently skipped.
    """
    conn = get_connection()
    cur = conn.cursor()
    saved = 0
    for a in articles:
        try:
            cur.execute("""
                INSERT INTO articles
                (title, author, url, published_at, source, category, description, summary, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title=VALUES(title), author=VALUES(author), published_at=VALUES(published_at),
                    source=VALUES(source), category=VALUES(category), description=VALUES(description),
                    summary=VALUES(summary), fetched_at=VALUES(fetched_at)
            """, (
                a.get("title"),
                a.get("author"),
                a.get("url") or a.get("link"),
                a.get("published_at") or a.get("published") or a.get("published_date"),
                a.get("source"),
                a.get("category"),
                a.get("description"),
                a.get("summary"),
                datetime.now(timezone.utc).isoformat(),
            ))
            saved += 1
        except Exception as e:
            print(f"Skipped one article due to error: {e}")
    conn.commit()
    cur.close()
    conn.close()
    print(f"Saved (or skipped duplicates of) {saved} articles to hosted MySQL")

def clear_selections(week_of=None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM selections
        WHERE week_of = %s
        """,
        (week_of or datetime.now(timezone.utc).date().isoformat(),)
    )
    conn.commit()
    cur.close()
    conn.close()

def mark_article(article_id, mark_type, week_of=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO selections (article_id, mark_type, week_of, created_at)
        VALUES (%s, %s, %s, %s)
    """, (
        article_id, mark_type,
        week_of or datetime.now(timezone.utc).date().isoformat(),
        datetime.now(timezone.utc).isoformat(),
    ))
    conn.commit()
    cur.close()
    conn.close()

def get_marked_articles(mark_type, week_of=None):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    if week_of is None:
        cur.execute("SELECT MAX(week_of) AS latest FROM selections WHERE mark_type = %s", (mark_type,))
        row = cur.fetchone()
        week_of = row["latest"] if row else None
    if week_of is None:
        cur.close(); conn.close()
        return []
    cur.execute("""
        SELECT articles.* FROM selections
        JOIN articles ON articles.id = selections.article_id
        WHERE selections.mark_type = %s AND selections.week_of = %s
    """, (mark_type, week_of))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def add_subscriber(name, email, contact_no, interests):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT IGNORE INTO subscribers (name, email, contact_no, interests, subscribed_at, active)
        VALUES (%s, %s, %s, %s, %s, TRUE)
    """, (
        name,
        email,
        contact_no,
        json.dumps(interests or []),
        datetime.now().isoformat(),
    ))
    conn.commit()
    cur.close()
    conn.close()

def get_subscriber_emails(active_only=True):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    if active_only:
        cur.execute("SELECT email FROM subscribers WHERE active = TRUE")
    else:
        cur.execute("SELECT email FROM subscribers")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r["email"] for r in rows]

def unsubscribe_subscriber(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE subscribers SET active = False WHERE email = %s", (email,))
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    init_db()