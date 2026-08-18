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
BASE_URL = os.getenv("BASE_URL", "")

HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NewsLetter</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: #f4f5f7;
            color: #1d1d1f;
            font-family: Arial, Helvetica, sans-serif;
        }
        table {
            border-collapse: collapse;
            border-spacing: 0;
        }
        a {
            text-decoration: none;
        }
        .wrapper {
            width: 100%;
            background-color: #f4f5f7;
        }
        .container {
            width: 100%;
            max-width: 720px;
            background-color: #ffffff;
        }

        /* HEADER */
        .nav {
            padding: 40px 30px;
            background-color: #ffffff;
            border-bottom: 1px solid #eaeaea;
        }
        .logo {
            font-size: 26px;
            line-height: 1;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #111111;
        }
        .edition {
            padding: 6px 12px;
            border: 1px solid #dddddd;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
            color: #666666; 
            text-transform: uppercase;
        }

        /* ARTICLE CARDS */
        .article-wrapper { padding: 16px 26px 0; }
        .article-card { 
            width: 100%; 
            border-radius: 4px; 
            border: 1px solid rgba(255,255,255,0.18); 
            box-shadow: 0 5px 16px rgba(0,0,0,0.22); 
        }
        .article-inner { padding: 28px 30px 26px; }
        .article-meta { font-size: 9px; line-height: 1.4; padding-bottom: 14px; }
        .article-number { color: #666d69; font-weight: 800; padding-right: 9px; }
        .article-category { color: #5148d9; font-weight: 800; letter-spacing: 1.2px; padding-right: 9px; }
        .article-date { color: #737a75; }
        .article-title { margin: 0; padding: 0; font-size: 24px; line-height: 1.22; letter-spacing: -0.5px; font-weight: 700; color: #191b1f; }
        .article-summary { margin: 0; padding-top: 12px; font-size: 13px; line-height: 1.65; color: #555a61; }
        .article-bottom { margin-top: 23px; padding-top: 15px; border-top: 1px solid rgba(0,0,0,0.08); }
        .article-source { font-size: 8px; font-weight: 800; letter-spacing: 1.1px; text-transform: uppercase; color: #686e6a; }
        .read-story { font-size: 9px; font-weight: 800; color: #363a40; }
        .arrow { color: #5148d9; padding-left: 3px; }

        /* FOOTER */
        .footer { padding: 42px 26px 50px; text-align: center; font-size: 9px; line-height: 1.9; color: #858e89; }
        .footer-brand { font-weight: 800; letter-spacing: 1px; color: #b6beb9; }
        .footer-links { margin-top: 7px; }
        .footer-link { color: #929b96; }

        /* MOBILE RESPONSIVENESS */
        @media only screen and (max-width: 600px) {
            .container { width: 100% !important; }
            .nav { padding: 30px 20px !important; }
            .logo { font-size: 22px !important; }
            .article-wrapper { padding-left: 16px !important; padding-right: 16px !important; padding-top: 13px !important; }
            .article-inner { padding: 24px 22px 22px !important; }
            .article-title { font-size: 21px !important; }
            .article-summary { font-size: 13px !important; }
            .footer { padding-left: 16px !important; padding-right: 16px !important; }
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
                    <td>
                        <div class="footer">
                            <div class="footer-brand">
                                NEWSLETTER - SOME DESCRIPTION
                            </div>
                            <div class="footer-links">
                                <a href="{unsubscribe_url}" class="footer-link">Manage interests</a>
                                &nbsp;&middot;&nbsp;
                                <a href="{unsubscribe_url}" class="footer-link">Unsubscribe</a>
                            </div>
                        </div>
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
        return "DATE UNKNOWN"

    raw_date = str(raw_date).strip()

    try:
        date_value = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        return date_value.strftime("%d %b %Y").upper()
    except (ValueError, TypeError):
        pass

    try:
        date_value = parsedate_to_datetime(raw_date)
        return date_value.strftime("%d %b %Y").upper()
    except (ValueError, TypeError):
        pass

    return "DATE UNKNOWN"

def build_news_body(articles, recipient_email, subscriber_id):
    send_date = datetime.now().strftime("%d %b %Y").upper()

    unsubscribe_url = f"{BASE_URL}/unsubscribe/{subscriber_id}" if BASE_URL else "#"

    # 1. Start HTML (leaves container table open)
    html_content = HTML_HEAD

    # 2. Add Dynamic Header Row
    html_content += f"""
                <tr>
                    <td class="nav">
                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                                <td align="left" valign="middle">
                                    <a href="#" class="logo">NewsLetter</a>
                                </td>
                                <td align="right" valign="middle">
                                    <span class="edition">{send_date}</span>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
    """

    # 3. Add Article Cards
    count = 1
    card_colors = ["#c9e2ee", "#f0d8b8", "#c9e3d1", "#dfcdea"]

    for article in articles:
        title = article.get("title")
        if not title:
            continue

        url = article.get("url") or "#"
        category = (article.get("category") or "TECH NEWS").upper()
        source = (article.get("source") or "UNKNOWN SOURCE")
        summary = (article.get("summary") or "")
        published_date = format_article_date(article.get("published_at"))

        safe_title = escape(str(title))
        safe_category = escape(str(category))
        safe_source = escape(str(source))
        safe_summary = escape(str(summary))
        safe_url = escape(str(url), quote=True)

        card_color = card_colors[(count - 1) % len(card_colors)]

        story_block = f"""
                <tr>
                    <td>
                        <div class="article-wrapper">
                            <table class="article-card" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: {card_color};">
                                <tr>
                                    <td>
                                        <div class="article-inner">
                                            
                                            <!-- ARTICLE META -->
                                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                                <tr>
                                                    <td>
                                                        <div class="article-meta">
                                                            <span class="article-number">{count:02d}</span>
                                                            <span class="article-category">{safe_category}</span>
                                                            <span class="article-date">{published_date}</span>
                                                        </div>
                                                    </td>
                                                </tr>
                                                
                                                <!-- ARTICLE TITLE -->
                                                <tr>
                                                    <td>
                                                        <a href="{safe_url}">
                                                            <div class="article-title">{safe_title}</div>
                                                        </a>
                                                    </td>
                                                </tr>
                                                
                                                <!-- ARTICLE SUMMARY -->
                                                <tr>
                                                    <td>
                                                        <div class="article-summary">{safe_summary}</div>
                                                    </td>
                                                </tr>
                                                
                                                <!-- ARTICLE FOOTER -->
                                                <tr>
                                                    <td>
                                                        <table class="article-bottom" width="100%" cellpadding="0" cellspacing="0" border="0">
                                                            <tr>
                                                                <td align="left">
                                                                    <div class="article-source">{safe_source}</div>
                                                                </td>
                                                                <td align="right">
                                                                    <a href="{safe_url}" class="read-story">
                                                                        Read story <span class="arrow">↗</span>
                                                                    </a>
                                                                </td>
                                                            </tr>
                                                        </table>
                                                    </td>
                                                </tr>
                                            </table>
                                        </div>
                                    </td>
                                </tr>
                            </table>
                        </div>
                    </td>
                </tr>
        """
        html_content += story_block
        count += 1

    # 4. Add Footer (closes container table)
    html_content += HTML_FOOTER.format(unsubscribe_url=unsubscribe_url)

    return html_content

def build_tech_of_week_body(pick):
    return f"TECH OF THE WEEK\n\n{pick.get('title', '')}\n\n{pick.get('description', '')}\n\nLink: {pick.get('link', '')}"

def build_topic_of_week_body(pick):
    return f"TOPIC OF THE WEEK\n\n{pick.get('title', '')}\n\n{pick.get('description', '')}\n\nLink: {pick.get('link', '')}"


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
            if html_email:
                personalized_body = body(email, subscriber_id);
                inlined_html = transform(personalized_body)
                msg = MIMEText(inlined_html, "html")
            else:
                msg = MIMEText(body, "plain")

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
            "Your Daily News Brief",
            lambda email, subscriber_id: build_news_body(
            news_articles,
            email,
            subscriber_id
        ),
            True
        )
        # Uncomment below if you want plain text separate emails:
        # (f"Tech of the Week: {tech_pick.get('title', '')}", build_tech_of_week_body(tech_pick), False),
        # (f"Topic of the Week: {topic_pick.get('title', '')}", build_topic_of_week_body(topic_pick), False)
    ]

    return [(subject, body, html_email) for subject, body, html_email in mails if body]

if __name__ == "__main__":
    if not SENDER_EMAIL or not APP_PASSWORD:
        print("mail/password not set in environment")
    else:
        for subject, body, html_email in build_newsletter_mails():
            send_to_all_subscribers(subject, body, html_email)

        print("Newsletter Project Run completed")