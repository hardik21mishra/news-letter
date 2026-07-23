from app import the_news
import os
import smtplib
from email.mime.text import MIMEText

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
SUBSCRIBERS_FILE = "subscribers.txt"

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        print("No subscribers.txt found - no one to send to.")
        return []
    with open(SUBSCRIBERS_FILE, "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

CATEGORY_COLORS = {
    "Politics": "#5B6C8F",
    "Technology": "#3E7C6B",
    "Sports": "#4F7942",
    "Business": "#8A6D3B",
    "World": "#7A5C4F",
    "Entertainment": "#8F5B7C",
    "Health": "#4F7C8A",
    "Science": "#5B7C8F",
    "Other": "#6B6B6B",
}
DEFAULT_COLOR = "#6B6B6B"

def build_article_block(article):
    color = CATEGORY_COLORS.get(article["category"], DEFAULT_COLOR)
    return f"""
<tr><td style="padding:0 40px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td width="4" style="background-color:{color};"></td>
    <td style="padding:24px 0 24px 20px;">
      <div style="font-family:Arial, Helvetica, sans-serif; font-size:11px; letter-spacing:2px; color:{color}; text-transform:uppercase; font-weight:bold;">{article['category']}</div>
      <div style="font-family:Georgia, 'Times New Roman', serif; font-size:19px; color:#16202A; font-weight:bold; margin-top:6px; line-height:1.3;">{article['title']}</div>
      <div style="font-family:Arial, Helvetica, sans-serif; font-size:14px; color:#4A5361; margin-top:10px; line-height:1.55;">{article['summary']}</div>
      <div style="margin-top:12px;">
        <a href="{article['link']}" style="font-family:Arial, Helvetica, sans-serif; font-size:13px; color:#C08829; text-decoration:none; font-weight:bold; border-bottom:1px solid #C08829; padding-bottom:1px;">Read the full story &rarr;</a>
      </div>
    </td>
  </tr>
  </table>
</td></tr>
<tr><td style="padding:0 40px;"><div style="border-top:1px solid #EEF1F5;"></div></td></tr>
"""
 

def build_body(articles):
    from datetime import datetime
    dateline = datetime.now().strftime("%A, %B %d, %Y").upper()
 
    blocks = ""
    count = 0
    for article in articles:
        if article["category"] is None or article["summary"] is None:
            continue
        blocks += build_article_block(article)
        count += 1
 
    intro = "Stories worth your morning coffee." if count else "No stories today - check back tomorrow."
 
    html = f"""
<html><body style="margin:0; padding:0; background-color:#EEF1F5;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#EEF1F5; padding:32px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#FFFFFF; border:1px solid #DDE2E8;">
 
<tr><td style="background-color:#16202A; padding:36px 40px 28px 40px;" align="center">
  <div style="font-family:Georgia, 'Times New Roman', serif; font-size:30px; letter-spacing:2px; color:#FFFFFF; text-transform:uppercase;">The Daily Brief</div>
  <div style="font-family:Georgia, 'Times New Roman', serif; font-size:12px; letter-spacing:3px; color:#C08829; text-transform:uppercase; margin-top:8px;">{dateline}</div>
</td></tr>
 
<tr><td style="padding:24px 40px 8px 40px; font-family:Georgia, 'Times New Roman', serif; font-size:14px; color:#4A5361; font-style:italic; border-bottom:1px solid #EEF1F5;">
  {intro}
</td></tr>
 
{blocks}
 
<tr><td style="background-color:#F7F8FA; padding:28px 40px; border-top:1px solid #DDE2E8;" align="center">
  <div style="font-family:Arial, Helvetica, sans-serif; font-size:12px; color:#8A93A3; line-height:1.6;">
    You're receiving this because you subscribed to The Daily Brief.<br>
    Curated automatically, delivered every morning.
  </div>
</td></tr>
 
</table>
</td></tr>
</table>
</body></html>
"""
    return html

def send_to_all_subscribers(body):
    subscribers = load_subscribers()

    if not subscribers:
        print("no subscribers availalele")
        return

    msg = MIMEText(body, "html")
    msg["Subject"] = "Your Daily News Brief"
    msg["From"] = SENDER_EMAIL

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        for email in subscribers:
            if "To" in msg:
                del msg["To"]
            msg["To"] = email
            server.sendmail(SENDER_EMAIL, email, msg.as_string())
            print(f"Sent to {email}")

if __name__ == "__main__":
    if not SENDER_EMAIL or not APP_PASSWORD:
        print("mail/passoword not set in environment")
    else:
        articles = the_news()
        body = build_body(articles)
        send_to_all_subscribers(body)
        print("Newsletter Project Run completed")