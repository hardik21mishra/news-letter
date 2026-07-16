import smtplib
import os
from email.mime.text import MIMEText
from app import the_news

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
SUBSCRIBERS_FILE = "subscribers.txt"


def load_subscribers():
    """Read all subscriber emails from file, one per line."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        print("No subscribers.txt found - no one to send to.")
        return []
    with open(SUBSCRIBERS_FILE, "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


def build_html_body(articles):
    """Builds one HTML-formatted digest from all processed articles."""
    html = "<html><body>"
    html += "<h2 style='color:#2c3e50;'>Your Daily News Digest</h2>"

    for article in articles:
        if article["category"] is None or article["summary"] is None:
            continue

        html += f"""
        <div style="margin-bottom:20px; padding:10px; border-left:4px solid #3498db;">
            <h3 style="margin:0;">{article['title']}</h3>
            <p style="color:#888; font-size:12px;">{article['category']}</p>
            <p>{article['summary']}</p>
            <a href="{article['link']}" style="color:#3498db;">Read more &rarr;</a>
        </div>
        """

    html += "</body></html>"
    return html


def send_to_all_subscribers(html_body):
    """Sends the same HTML digest to every email in subscribers.txt."""
    subscribers = load_subscribers()

    if not subscribers:
        return

    msg = MIMEText(html_body, "html")
    msg["Subject"] = "Your Daily News Digest"
    msg["From"] = SENDER_EMAIL

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)

        for email in subscribers:
            msg["To"] = email
            server.sendmail(SENDER_EMAIL, email, msg.as_string())
            print(f"Sent to {email}")


if __name__ == "__main__":
    if not SENDER_EMAIL or not APP_PASSWORD:
        print("WARNING: SENDER_EMAIL or EMAIL_APP_PASSWORD not set in environment.")
    else:
        articles = the_news()
        html_body = build_html_body(articles)
        send_to_all_subscribers(html_body)
        print("Newsletter run complete.")