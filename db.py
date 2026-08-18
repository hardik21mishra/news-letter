# Env vars MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
import os
import mysql.connector
from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

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
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title TEXT,
            author TEXT,
            url VARCHAR(768) UNIQUE,
            published_at DATETIME,
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
        article_id INT NOT NULL,
        mark_type VARCHAR(50) NOT NULL,
        created_at TEXT,
        UNIQUE KEY unique_article_mark (article_id, mark_type),
        FOREIGN KEY (article_id) REFERENCES articles(id)
    );
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
    Accepts a list of article dicts in the normalized shape
    """
    conn = get_connection()
    cur = conn.cursor()
    saved = 0
    for a in articles:
        try:
            published_at_value = a.get("published_at")
            if published_at_value is None:
                published_at_value = a.get("published")

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
                published_at_value,
                a.get("source"),
                a.get("category"),
                a.get("description"),
                a.get("summary"),
                datetime.now(IST).replace(tzinfo=None),
            ))
            saved += 1
        except Exception as e:
            print(f"Skipped one article due to error: {e}")
    conn.commit()
    cur.close()
    conn.close()
    print(f"Saved (or skipped duplicates of) {saved} articles to hosted MySQL")

def clear_selections():
    return None

def mark_article(article_id, mark_type):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT IGNORE INTO selections (article_id, mark_type, created_at)
        VALUES (%s, %s, %s)
    """, (
        article_id,
        mark_type,
        datetime.now(timezone.utc).isoformat(),
    ))
    conn.commit()
    cur.close()
    conn.close()

def get_marked_articles(mark_type):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT articles.* FROM selections
        JOIN articles ON articles.id = selections.article_id
        WHERE selections.mark_type = %s
        ORDER BY articles.published_at DESC, articles.fetched_at DESC
    """, (mark_type,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def add_subscriber(name, email, contact_no, interests):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT IGNORE INTO subscribers (name, email, contact_no, interests, subscribed_at, active)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        name,
        email,
        contact_no,
        json.dumps(interests or []),
        datetime.now().isoformat(),
        True,
    ))
    conn.commit()
    cur.close()
    conn.close()

def get_subscriber_emails(active_only=True):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if active_only:
        cur.execute("""
            SELECT id, email
            FROM subscribers
            WHERE active = TRUE
        """)
    else:
        cur.execute("""
            SELECT id, email
            FROM subscribers
        """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def unsubscribe_subscriber(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE subscribers SET active = False
        WHERE id = %s
    """, (user_id,))

    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    init_db()