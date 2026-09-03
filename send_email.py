import os
import smtplib
from html import escape
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from datetime import datetime

from db import get_marked_articles, get_subscriber_emails
from premailer import transform

from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

# Temporarily disabled to allow the scheduled newsletter job to run before the app is publicly deployed.
# Once the backend is live, set BASE_URL to the public app URL, e.g. https://newsletter.example.com
# BASE_URL = os.getenv(
#     "BASE_URL",
#     "http://127.0.0.1:8000"
# )
BASE_URL = os.getenv("BASE_URL") or "http://127.0.0.1:8000"

HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Tech Newsletter</title>
    <style>
        body { margin: 0; padding: 0; background-color: #f4f5f7; color: #1a1a1a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        table { border-collapse: collapse; border-spacing: 0; width: 100%; }
        a { text-decoration: none; }
        
        .wrapper { background-color: #f4f5f7; padding: 20px 0; }
        .container { max-width: 600px; margin: 0 auto; background-color: #ffffff; overflow: hidden; }
        
        .header { background-color: #000000; padding: 30px 40px; text-align: center; border-bottom: 4px solid #00ff00; }
        .logo-text { color: #ffffff; font-size: 28px; font-weight: 900; letter-spacing: 1px; margin: 0; font-family: "Courier New", Courier, monospace; text-transform: uppercase; }
        .logo-accent { color: #00ff00; }
        .tagline { color: #cccccc; font-size: 13px; margin-top: 8px; font-family: -apple-system, sans-serif; }
        
        .intro-section { padding: 40px 40px 30px; }
        .greeting { font-size: 22px; font-weight: 800; color: #000000; margin: 0 0 15px 0; }
        .date-text { font-size: 15px; color: #333333; line-height: 1.6; margin: 0 0 20px 0; }
        
        .history-section { background-color: #f9f9f9; border-left: 4px solid #00ff00; padding: 15px 20px; }
        .history-heading { font-size: 14px; font-weight: 800; color: #000000; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 8px 0; }
        .history-text { font-size: 14px; color: #444444; line-height: 1.5; margin: 0; }

        .article-block { padding: 30px 40px; border-top: 1px solid #eeeeee; }
        .article-meta { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #666666; margin-bottom: 12px; }
        .article-category { color: #000000; background-color: #00ff00; padding: 3px 8px; font-weight: 800; margin-right: 8px; display: inline-block; }
        .article-title { font-size: 24px; font-weight: 800; color: #000000; line-height: 1.3; margin: 0 0 12px 0; letter-spacing: -0.5px; }
        .article-summary { font-size: 15px; color: #444444; line-height: 1.6; margin: 0 0 15px 0; }
        .tldr { font-weight: 800; color: #000000; }
        
        .read-more-container { text-align: center; margin-top: 25px; margin-bottom: 10px; }
        .read-more { display: inline-block; font-size: 13px; font-weight: 800; color: #000000; text-transform: uppercase; letter-spacing: 1px; padding: 10px 24px; border: 2px solid #000000; text-decoration: none; transition: background-color 0.2s, color 0.2s; }

        .footer { padding: 40px; background-color: #f9f9f9; text-align: center; border-top: 1px solid #eeeeee; }
        .footer-text { color: #888888; font-size: 12px; line-height: 1.6; margin: 0; }
        .footer-links a { color: #555555; text-decoration: underline; margin: 0 10px; }

        @media only screen and (max-width: 600px) {
            .header, .intro-section, .article-block, .footer { padding-left: 20px !important; padding-right: 20px !important; }
            .article-title { font-size: 22px !important; }
        }
    </style>
</head>
<body>
<table class="wrapper" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
        <td align="center">
            <table class="container" width="100%" cellpadding="0" cellspacing="0" border="0">
"""

HTML_FOOTER = """
            </table>
            
            <table class="container" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f5f7;">
                <tr>
                    <td class="footer">
                        <p class="footer-text">
                            You are receiving this because you subscribed to our tech updates.<br><br>
                            <span class="footer-links">
                                <a href="{unsubscribe_url}">Manage Interests</a> | 
                                <a href="{unsubscribe_url}">Unsubscribe</a>
                            </span>
                        </p>
                    </td>
                </tr>
            </table>

        </td>
    </tr>
</table>
</body>
</html>
"""

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

def build_news_body(articles, recipient_email, subscriber_id):
    current_time = datetime.now()
    send_date_str = current_time.strftime("%B %d, %Y")

    # Extract the 'On This Day' item and separate standard articles
    history_fact = "The Mozilla Corporation was established by co-founders Mitchell Baker and Brendan Eich as a taxable subsidiary of the non-profit Mozilla Foundation to better fund, manage, and expand the development of the popular Firefox web browser."
    
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
    html_content += f"""
                <tr>
                    <td class="header">
                        <p class="logo-text">THE <span class="logo-accent">TECH</span> NEWSLETTER</p>
                        <p class="tagline">Your Dose of Electrifying Tech Content</p>
                    </td>
                </tr>
                <tr>
                    <td class="intro-section">
                        <h2 class="greeting">How are you, @hacker?</h2>
                        <p class="date-text">🪐 What's happening in tech today, {send_date_str}?</p>
                        <div class="history-section">
                            <h3 class="history-heading">On This Day</h3>
                            <p class="history-text">{safe_history}</p>
                        </div>
                    </td>
                </tr>
    """

    for article in standard_articles:
        title = article.get("title")
        if not title:
            continue

        url = article.get("url") or "#"
        category = (article.get("category") or "TECH").upper()
        summary = (article.get("summary") or "")
        published_date = format_article_date(article.get("published_at"))
        
        date_display = f" &middot; {published_date}" if published_date else ""

        safe_title = escape(str(title))
        safe_category = escape(str(category))
        safe_summary = escape(str(summary))
        safe_url = escape(str(url), quote=True)

        html_content += f"""
                <tr>
                    <td class="article-block">
                        <div class="article-meta">
                            <span class="article-category">{safe_category}</span>{date_display}
                        </div>
                        <a href="{safe_url}">
                            <h3 class="article-title">{safe_title}</h3>
                        </a>
                        <p class="article-summary">
                            <span class="tldr">TL;DR</span> {safe_summary}
                        </p>
                        <div class="read-more-container">
                            <a href="{safe_url}" class="read-more">Read More</a>
                        </div>
                    </td>
                </tr>
        """

    html_content += HTML_FOOTER.format(unsubscribe_url=unsubscribe_url)
    return html_content

def build_tech_of_week_body(pick):
    return f"TECH OF THE WEEK\n\n{pick.get('title', '')}\n\n{pick.get('description', '')}\n\nLink: {pick.get('link', '')}"

def build_topic_of_week_body(pick):
    return f"TOPIC OF THE WEEK\n\n{pick.get('title', '')}\n\n{pick.get('description', '')}\n\nLink: {pick.get('link', '')}"

def render_email_body(body, recipient_email, subscriber_id, html_email):
    if html_email:
        return transform(body(recipient_email, subscriber_id))
    return body

def send_to_all_subscribers(subject, body, html_email=True):
    subscribers = get_subscriber_emails()

    if not subscribers:
        print("No subscribers available")
        return

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

def build_newsletter_mails():
    news_articles = get_marked_articles("news")
    tech_picks = get_marked_articles("tech_of_week")
    topic_picks = get_marked_articles("topic_of_week")

    tech_pick = tech_picks[0] if tech_picks else {}
    topic_pick = topic_picks[0] if topic_picks else {}

    mails = [
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