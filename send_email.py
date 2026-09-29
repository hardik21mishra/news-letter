import os
import smtplib
from collections.abc import Callable
from pathlib import Path
from html import escape
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from datetime import datetime

from db import get_selected_articles, get_subscriber_emails
from premailer import transform

from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

BASE_URL = os.getenv("BASE_URL") or "http://127.0.0.1:8000"

# Load templates once, relative to this module rather than the working directory.
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "email"

HTML_HEAD = (TEMPLATE_DIR / "head.html").read_text(encoding="utf-8")

HTML_FOOTER = (TEMPLATE_DIR / "footer.html").read_text(encoding="utf-8")
HTML_INTRO = (TEMPLATE_DIR / "intro.html").read_text(encoding="utf-8")
HTML_ARTICLE = (TEMPLATE_DIR / "article.html").read_text(encoding="utf-8")
TECH_OF_WEEK_TEMPLATE = (TEMPLATE_DIR / "tech_of_week.txt").read_text(encoding="utf-8")
TOPIC_OF_WEEK_TEMPLATE = (TEMPLATE_DIR / "topic_of_week.txt").read_text(encoding="utf-8")

def format_article_date(raw_date):
    if not raw_date:
        return ""

    raw_date = str(raw_date).strip()

    try:
        date_value = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        return date_value.strftime("%b %d, %Y").upper()
    except (ValueError, TypeError):
        pass

    try:
        date_value = parsedate_to_datetime(raw_date)
        return date_value.strftime("%b %d, %Y").upper()
    except (ValueError, TypeError):
        pass

    return ""

def build_news_body(articles, recipient_email, subscriber_id, platform="email"):
    current_time = datetime.now()
    send_date_str = current_time.strftime("%B %d, %Y")

    # Extract the 'On This Day' item and separate standard articles
    history_fact = "the Apple Lisa was introduced as one of the first personal computers featuring a graphical user interface (GUI) and a computer mouse"
    standard_articles = []
    
    for article in articles:
        if str(article.get("category", "")).upper() == "HISTORY":
            history_fact = article.get("summary", history_fact)
        else:
            standard_articles.append(article)

    unsubscribe_url = f"{BASE_URL}/unsubscribe/{subscriber_id}" if BASE_URL else "#"
    
    html_content = HTML_HEAD
    safe_history = escape(str(history_fact))

    # Intro Section with On This Day Block
    html_content += HTML_INTRO.format(
        send_date_str=send_date_str,
        safe_history=safe_history,
    )

    for article in standard_articles:
        title = article.get("title")
        if not title:
            continue

        url = article.get("url") or "#"
        article_id = article.get("id")
        tracking_url = (
            f"{BASE_URL}/track/{subscriber_id or 0}/{article_id}?platform={platform}"
            if BASE_URL and article_id and platform in {"telegram", "discord"}
            else url
        )
        if BASE_URL and article_id and platform == "email" and subscriber_id:
            tracking_url = f"{BASE_URL}/track/{subscriber_id}/{article_id}?platform=email"
        category = (article.get("category") or "TECH NEWS").upper()
        source = (article.get("source") or "UNKNOWN SOURCE")
        summary = (article.get("summary") or "")
        published_date = format_article_date(article.get("published_at"))
        
        date_display = f" &middot; {published_date}" if published_date else ""

        safe_title = escape(str(title))
        safe_category = escape(str(category))
        safe_summary = escape(str(summary))
        safe_url = escape(str(tracking_url), quote=True)

        html_content += HTML_ARTICLE.format(
            safe_category=safe_category,
            date_display=date_display,
            safe_url=safe_url,
            safe_title=safe_title,
            safe_summary=safe_summary,
        )

    html_content += HTML_FOOTER.format(unsubscribe_url=unsubscribe_url)
    return html_content

def build_tech_of_week_body(pick):
    return TECH_OF_WEEK_TEMPLATE.format(
        title=pick.get('title', ''),
        description=pick.get('description', ''),
        link=pick.get('link', ''),
    )

def build_topic_of_week_body(pick):
    return TOPIC_OF_WEEK_TEMPLATE.format(
        title=pick.get('title', ''),
        description=pick.get('description', ''),
        link=pick.get('link', ''),
    )

def render_email_body(body, recipient_email, subscriber_id, html_email):
    if html_email:
        return transform(body(recipient_email, subscriber_id))
    return body

def send_to_all_subscribers(subject, body, html_email=True):
    subscribers = get_subscriber_emails()

    if not subscribers:
        print("No subscribers available")
        return

    if SENDER_EMAIL is None or APP_PASSWORD is None:
        raise RuntimeError("SENDER_EMAIL and EMAIL_APP_PASSWORD must be set before sending email.")

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)

        for subscriber in subscribers:
            subscriber_id = subscriber["id"]
            email = subscriber["email"]
            rendered_body = render_email_body(
                body, email, subscriber_id, html_email
            )
            if html_email:
                msg = MIMEText(rendered_body, "html")
            else:
                msg = MIMEText(rendered_body, "plain")

            msg["Subject"] = subject
            msg["From"] = SENDER_EMAIL
            msg["To"] = email

            server.sendmail(SENDER_EMAIL, email, msg.as_string())
            print(f"Sent '{subject}' to {email}")

def build_newsletter_mails(selected_articles=None):
    selected_articles = selected_articles if selected_articles is not None else get_selected_articles()
    news_articles = [article for article in selected_articles if article["mark_type"] == "news"]
    tech_picks = [article for article in selected_articles if article["mark_type"] == "tech_of_week"]
    topic_picks = [article for article in selected_articles if article["mark_type"] == "topic_of_week"]

    tech_pick = tech_picks[0] if tech_picks else {}
    topic_pick = topic_picks[0] if topic_picks else {}

    mails: list[tuple[str, str | Callable[[str, int | None], str], bool]] = [
        (
            "Your Daily Tech Brief",
            lambda email, subscriber_id: build_news_body(
                news_articles,
                email,
                subscriber_id
            ),
            True
        )
    ]

    if tech_pick:
        mails.append((
            f"Tech of the Week: {tech_pick.get('title', '')}",
            build_tech_of_week_body(tech_pick),
            False,
        ))
    if topic_pick:
        mails.append((
            f"Topic of the Week: {topic_pick.get('title', '')}",
            build_topic_of_week_body(topic_pick),
            False,
        ))

    return [(subject, body, html_email) for subject, body, html_email in mails if body]


if __name__ == "__main__":
    if not SENDER_EMAIL or not APP_PASSWORD:
        print("mail/password not set in environment")
    else:
        for subject, body, html_email in build_newsletter_mails():
            send_to_all_subscribers(subject, body, html_email)

        print("Newsletter Project Run completed")
