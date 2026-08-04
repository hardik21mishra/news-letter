import os
import smtplib
import openpyxl
from email.mime.text import MIMEText
from datetime import datetime

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
SUBSCRIBERS_FILE = "subscribers.txt"
EXCEL_FILE = "tech_top_news.xlsx"

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        print("No subscribers.txt found - no one to send to.")
        return []
    with open(SUBSCRIBERS_FILE, "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def read_sheet_as_dicts(ws):
    rows = list(ws.iter_rows(values_only=True))
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:] if any(row)]

def build_news_body(articles):
    dateline = datetime.now().strftime("%A, %B %d, %Y").upper()
    lines = [f"THE DAILY BRIEF - {dateline}", ""]
    count = 0
    for a in articles:
        if not a.get("Title"):
            continue
        lines.append(a.get("Title", ""))
        lines.append(f"Source: {a.get('Source', '')} | {a.get('Published date', '')}")
        lines.append(a.get("Description", ""))
        lines.append("-" * 40)
        count += 1
    if count == 0:
        lines.append("No stories today - check back tomorrow.")
    return "\n".join(lines)


def build_tech_of_week_body(pick):
    return (
        f"TECH OF THE WEEK\n\n"
        f"{pick.get('Title', '')}\n\n"
        f"{pick.get('Description', '')}\n\n"
        f"Why it matters: {pick.get('Why it matters', '')}\n\n"
        f"Link: {pick.get('Link', '')}"
    )


def build_paper_of_week_body(pick):
    return (
        f"PAPER OF THE WEEK\n\n"
        f"{pick.get('Title', '')}\n"
        f"Authors: {pick.get('Authors', '')}\n\n"
        f"{pick.get('Description', '')}\n\n"
        f"Link: {pick.get('Link', '')}"
    )


def build_topic_of_week_body(pick):
    return (
        f"TOPIC OF THE WEEK\n\n"
        f"{pick.get('Title', '')}\n\n"
        f"{pick.get('Explanation', '')}\n\n"
        f"Link: {pick.get('Link', '')}"
    )


def send_to_all_subscribers(subject, body):
    subscribers = load_subscribers()

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
        wb = openpyxl.load_workbook(EXCEL_FILE)

        news_articles = read_sheet_as_dicts(wb["Sheet1"])
        tech_pick = read_sheet_as_dicts(wb["Tech of the Week"])[0]
        paper_pick = read_sheet_as_dicts(wb["Paper of the Week"])[0]
        topic_pick = read_sheet_as_dicts(wb["Topic of the Week"])[0]

        mails = [
            ("Your Daily News Brief", build_news_body(news_articles)),
            (f"Tech of the Week: {tech_pick.get('Title', '')}", build_tech_of_week_body(tech_pick)),
            (f"Paper of the Week: {paper_pick.get('Title', '')}", build_paper_of_week_body(paper_pick)),
            (f"Topic of the Week: {topic_pick.get('Title', '')}", build_topic_of_week_body(topic_pick)),
        ]

        for subject, body in mails:
            send_to_all_subscribers(subject, body)

        print("Newsletter Project Run completed")