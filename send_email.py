from app import the_news
import os
import smtplib
from email.mime.text import MIMEText

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
SUBSCRIBERS_FILE = "subscribers.txt"

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        print("there is no one to send to.")
        return []
    with open(SUBSCRIBERS_FILE, "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def build_body(articles):
    text = "Your Daily News Digest\n\n"

    for article in articles:
        if article["category"] is None or article["summary"] is None:
            continue

        text += article["title"] + "\n"
        text += "Category: " + article["category"] + "\n"
        text += article["summary"] + "\n"
        text += "Read more: " + article["link"] + "\n\n"
    return text

def send_to_all_subscribers(body):
    """Sends the same HTML digest to every email in subscribers.txt."""
    subscribers = load_subscribers()

    if not subscribers:
        return

    msg = MIMEText(body)
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
        print("SENDER_EMAIL or EMAIL_APP_PASSWORD not set in environment")
    else:
        articles = the_news()
        body = build_body(articles)
        send_to_all_subscribers(body)
        print("Newsletter Project Run completed")