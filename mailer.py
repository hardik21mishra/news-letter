import smtplib
import os
from email.mime.text import MIMEText
from dotenv import load_dotenv
load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

def send_single_email(to_email, subject, body):
    if not SENDER_EMAIL or not APP_PASSWORD:
        print("WARNING: SENDER_EMAIL or EMAIL_APP_PASSWORD not set.")
        return False

    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        print(f"Sent to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send to {to_email}: {e}")
        return False