# Env vars MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
import os
import tempfile
import mysql.connector
from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

from dotenv import load_dotenv
load_dotenv()


def get_required_env(name):
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_connection():
    host = get_required_env("MYSQL_HOST")
    ca_cert_path = os.getenv("MYSQL_SSL_CA")
    temporary_ca_path = None
    verify_ssl_setting = os.getenv("MYSQL_SSL_VERIFY_CERT")
    verify_ssl = (
        bool(ca_cert_path)
        if verify_ssl_setting is None
        else verify_ssl_setting.strip().lower() in {"1", "true", "yes"}
    )

    if ca_cert_path and "-----BEGIN CERTIFICATE-----" in ca_cert_path:
        ca_cert = ca_cert_path.replace("\\n", "\n")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pem", delete=False, encoding="ascii"
        ) as cert_file:
            cert_file.write(ca_cert)
            ca_cert_path = cert_file.name
            temporary_ca_path = ca_cert_path

    connect_args = dict(
        host=host,
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=get_required_env("MYSQL_USER"),
        password=get_required_env("MYSQL_PASSWORD"),
        database=get_required_env("MYSQL_DATABASE"),
        charset="utf8mb4",
        autocommit=False,
        use_pure=True,
    )

    # Aiven MySQL requires TLS and a CA certificate for secure connections.
    if host.endswith(".aivencloud.com"):
        if verify_ssl and not ca_cert_path:
            raise RuntimeError(
                "Aiven MySQL requires MYSQL_SSL_CA to be set to the CA certificate file path. "
                "Add it to your .env or GitHub Actions secrets."
            )
        if verify_ssl and "-----BEGIN CERTIFICATE-----" not in ca_cert_path and not os.path.isfile(ca_cert_path):
            raise RuntimeError(f"MYSQL_SSL_CA file does not exist: {ca_cert_path}")
        connect_args.update(
            {
                "ssl_disabled": False,
                "ssl_verify_cert": verify_ssl,
                "ssl_verify_identity": verify_ssl,
            }
        )
        if verify_ssl:
            connect_args["ssl_ca"] = ca_cert_path
    elif ca_cert_path:
        connect_args.update(
            {
                "ssl_disabled": False,
                "ssl_verify_cert": True,
                "ssl_ca": ca_cert_path,
            }
        )

    try:
        return mysql.connector.connect(**connect_args)
    finally:
        if temporary_ca_path:
            os.unlink(temporary_ca_path)

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS analytics (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subscriber_id INT NULL,
            interest VARCHAR(255) NOT NULL,
            platform VARCHAR(20) NOT NULL DEFAULT 'email',
            click_count INT NOT NULL DEFAULT 0,
            last_clicked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_subscriber_interest_platform (subscriber_id, interest, platform),
            FOREIGN KEY (subscriber_id) REFERENCES subscribers(id)
        )
    """)

    conn.commit()
    cur.close()
    conn.close()
    print(f"MySQL tables ready on {os.getenv('MYSQL_HOST', 'unknown host')}")

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

def get_selected_articles():
    today = datetime.now(timezone.utc).date()
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT articles.*, selections.mark_type
        FROM selections
        JOIN articles ON articles.id = selections.article_id
        WHERE selections.mark_type IN ('news', 'tech_of_week', 'topic_of_week')
          AND DATE(selections.created_at) = %s
        ORDER BY articles.published_at DESC, articles.fetched_at DESC
    """, (today,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def track_newsletter_click(subscriber_id, article_id, platform="email"):
    platform = platform.lower()
    if platform not in {"email", "telegram", "discord"}:
        platform = "email"
    analytics_subscriber_id = subscriber_id if platform == "email" else None

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
         SELECT articles.url, articles.category, subscribers.interests,
             subscribers.id AS subscriber_id
        FROM articles
        LEFT JOIN subscribers ON subscribers.id = %s
        WHERE articles.id = %s
    """, (subscriber_id, article_id))
    row = cur.fetchone()
    if not row or (platform == "email" and row.get("subscriber_id") is None):
        cur.close()
        conn.close()
        return None

    interests = []
    if row["interests"]:
        try:
            interests = json.loads(row["interests"])
        except (TypeError, json.JSONDecodeError):
            pass
    if not isinstance(interests, list):
        interests = []

    category = (row["category"] or "").strip()
    if category and not any(
        str(interest).strip().lower() == category.lower()
        for interest in interests
    ):
        interests.append(category)

    if category:
        cur.execute("""
            SELECT id FROM analytics
            WHERE subscriber_id <=> %s AND interest = %s AND platform = %s
            FOR UPDATE
        """, (analytics_subscriber_id, category, platform))
        existing = cur.fetchone()
        if existing:
            cur.execute("""
                UPDATE analytics
                SET click_count = click_count + 1, last_clicked_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (existing["id"],))
        else:
            cur.execute("""
                INSERT INTO analytics
                    (subscriber_id, interest, platform, click_count, last_clicked_at)
                VALUES (%s, %s, %s, 1, CURRENT_TIMESTAMP)
            """, (analytics_subscriber_id, category, platform))
    if subscriber_id:
        cur.execute("""
            UPDATE subscribers
            SET interests = %s
            WHERE id = %s
        """, (json.dumps(interests), subscriber_id))
    conn.commit()
    cur.close()
    conn.close()
    return row["url"]

def get_article_url(article_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT url FROM articles WHERE id = %s", (article_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

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

def get_subscriber_id_by_email(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM subscribers WHERE email = %s", (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

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