import os
import smtplib
from db import get_marked_articles, get_subscriber_emails
from email.mime.text import MIMEText
from datetime import datetime

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
SUBSCRIBERS_FILE = "subscribers.txt"
EXCEL_FILE = "tech_top_news.xlsx"

def build_news_body(articles):
    dateline = datetime.now().strftime("%A, %B %d, %Y").upper()
    lines = [f"THE DAILY BRIEF - {dateline}", ""]
    count = 0
    for a in articles:
        if not a.get("title"):
            continue
        lines.append(a.get("title", ""))
        lines.append(f"Source: {a.get('source', '')} | {a.get('published_date', '')}")
        # lines.append(a.get("description", ""))
        lines.append(a.get("summary", ""))
        lines.append("-" * 40)
        count += 1
    if count == 0:
        lines.append("No stories today - check back tomorrow.")
    return "\n".join(lines)

def build_tech_of_week_body(pick):
    return (
        f"TECH OF THE WEEK\n\n"
        f"{pick.get('title', '')}\n\n"
        f"{pick.get('description', '')}\n\n"
        f"Link: {pick.get('link', '')}"
    )

def build_topic_of_week_body(pick):
    return (
        f"TOPIC OF THE WEEK\n\n"
        f"{pick.get('title', '')}\n\n"
        f"{pick.get('description', '')}\n\n"
        f"Link: {pick.get('link', '')}"
    )

def send_to_all_subscribers(subject, body):
    subscribers = get_subscriber_emails()

    if not subscribers:
        print("no subscribers available")
        return

    msg = MIMEText(body)  # plain text, no "html" subtype -- no design, just content
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        for email in subscribers:
            if "To" in msg:
                del msg["To"]
            msg["To"] = email
            server.sendmail(SENDER_EMAIL, email, msg.as_string())
            print(f"Sent '{subject}' to {email}")

if __name__ == "__main__":
    if not SENDER_EMAIL or not APP_PASSWORD:
        print("mail/password not set in environment")
    else:
        news_articles = get_marked_articles("news")
        # tech_picks = get_marked_articles("tech_of_week")
        # topic_picks = get_marked_articles("topic_of_week")

        # tech_pick = tech_picks[0] if tech_picks else {}
        # topic_pick = topic_picks[0] if topic_picks else {}

        mails = [
            ("Your Daily News Brief", build_news_body(news_articles))
            # ,
            # (f"Tech of the Week: {tech_pick.get('title', '')}", build_tech_of_week_body(tech_pick)),
            # (f"Topic of the Week: {topic_pick.get('title', '')}", build_topic_of_week_body(topic_pick)),
        ]

        for subject, body in mails:
            if not body.strip():
                continue
            send_to_all_subscribers(subject, body)

        print("Newsletter Project Run completed")