from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from app import the_news
from datetime import datetime
from typing import List
from apscheduler.schedulers.background import BackgroundScheduler
from send_email import build_body
from mailer import send_single_email

app = FastAPI()

SUBSCRIBERS_FILE = "subscribers.txt"
 

scheduler = BackgroundScheduler()         #this
scheduler.start()                        #this

class SubscribeRequest(BaseModel):
    email: EmailStr

class SendEmailRequest(BaseModel): #this
    emails: List[EmailStr] #this
    send_st: datetime | None = None  # this #--> sends at current time(immediately) if the time is not mentioneeed by the user


@app.get("/")
def home():
    return {"message": "Helloooo, this is my news API"}
  
@app.get("/news")
def get_news(category: str = None):
    articles = the_news() 
    if category:
        articles = [a for a in articles if a["category"] == category] 
    return articles

@app.post("/subscribe")
def subscribe(request: SubscribeRequest):
    email = request.email
    existing = []
    with open(SUBSCRIBERS_FILE, "r") as f:
        existing = [line.strip() for line in f.readlines() if line.strip()]
    
    if email in existing:
        raise HTTPException(status_code=400, detail="Email is already subscribed")
 
    with open(SUBSCRIBERS_FILE, "a") as f:
        f.write(email + "\n")
    return {f"{email} subscribed successfully"}

def send(emails):
    articles = the_news()
    body = build_body(articles)

    results = []
    for email in emails:
        success = send_single_email(email, "The Daily Brief", body)
        results.append({"email": email, "sent": success})

    return results

@app.post("/send-email")
def send_email_endpoint(request: SendEmailRequest):
    now = datetime.now()
    
    if request.send_st is None or request.send_st <= now:
        results = send(request.emails)
        return {"message": "Email(s) send immediately", "results": results}
    else:
        scheduler.add_job(
            send,
            "date",
            run_date = request.send_at,
            args = [request.emails],
        )
        return {
            "message": f"Email(s) scheduled for {len(request.emails)} recipient(s) at {request.send_at.isoformat()}"
        }
    