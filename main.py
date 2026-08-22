from fastapi import FastAPI
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone
from typing import List, Optional
from send_email import build_newsletter_mails, send_to_all_subscribers, render_email_body
from apscheduler.schedulers.background import BackgroundScheduler
from mailer import send_single_email
from db import (
    add_subscriber,
    get_marked_articles,
    get_subscriber_id_by_email,
    track_newsletter_click,
    unsubscribe_subscriber,
)
from google_sheets import download_sheet_xlsx, get_sheet_id
import uvicorn

app = FastAPI()
scheduler = BackgroundScheduler()        
scheduler.start()                       

class SubscribeRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    contact_no: Optional[str] = None
    interests: list[str] = []

class SendEmailRequest(BaseModel): 
    emails: List[EmailStr] 
    send_at: datetime | None = None  

class BroadcastRequest(BaseModel):
    send_at: datetime | None = None

@app.get("/")
def home():
    return {"message": "Helloooo, this is my news API"}
  
@app.get("/news")
def get_news():
    return get_marked_articles("news")

@app.post("/subscribe")
def subscribe(request: SubscribeRequest):
    add_subscriber(
        request.name,
        request.email,
        request.contact_no,
        request.interests
    )
    return {
        "message" : "Subscribed successfully"
    }

@app.get("/unsubscribe/{user_id}")
def unsubscribe(user_id: int):
    unsubscribe_subscriber(user_id)

    return {
        "message": "You have been successfully unsubscribed."
    }

@app.get("/track/{subscriber_id}/{article_id}")
def track_click(subscriber_id: int, article_id: int):
    article_url = track_newsletter_click(subscriber_id, article_id)
    if not article_url:
        return Response(content="Subscriber or article not found", status_code=404)

    return RedirectResponse(url=article_url, status_code=307)

def broadcast_now():
    results = []
    for subject, body, html_email in build_newsletter_mails():
        send_to_all_subscribers(subject, body, html_email)
        results.append({"subject": subject, "sent": True})
    return results

@app.post("/broadcast")
def broadcast_endpoint(request: BroadcastRequest):
    now = datetime.now(timezone.utc)
    send_at = request.send_at
    if send_at is not None and send_at.tzinfo is None:
        send_at = send_at.replace(tzinfo=timezone.utc)
    if send_at is None or send_at <= now:
        results = broadcast_now()
        return {
            "message": "Newsletter broadcast send immediately", "results": results
        }
    else:
        scheduler.add_job(broadcast_now, "date", run_date=send_at)
        return {"message": f"Newsletter broadcast scheduled for {send_at.isoformat()}"}

def send_on_demand(emails):
    results = []
    for email in emails:
        subscriber_id = get_subscriber_id_by_email(email)
        for subject, body, html_email in build_newsletter_mails():
            rendered_body = render_email_body(body, email, subscriber_id, html_email)
            success = send_single_email(email, subject, rendered_body, html_email)
            results.append({"email": email, "subject": subject, "sent": success})
    return results

@app.post("/send-email")
def send_email_endpoint(request: SendEmailRequest):
    now = datetime.now(timezone.utc)
    send_at = request.send_at
    if send_at is not None and send_at.tzinfo is None:
        send_at = send_at.replace(tzinfo=timezone.utc)

    if send_at is None or send_at <= now:
        results = send_on_demand(request.emails)
        return {"message": "Email(s) send immediately", "results": results}
    else:
        scheduler.add_job(
            send_on_demand,
            "date",
            run_date = send_at,
            args = [request.emails],
        )
        return {
            "message": f"Email(s) scheduled for {len(request.emails)} recipient(s) at {send_at.isoformat()}"
        }

@app.get("/get_sheet")
def download_sheet():
    return Response(
        content=download_sheet_xlsx(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="newsletter.xlsx"'
        },
    )

@app.get("/sheet_link")
def open_curator_sheet():
    sheet_url = f"https://docs.google.com/spreadsheets/d/{get_sheet_id()}/edit"
    return RedirectResponse(url=sheet_url, status_code=307)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)