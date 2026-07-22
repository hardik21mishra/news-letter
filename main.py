from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from app import the_news
from db import init_db, add_subscriber, subscriber_count

app = FastAPI()

init_db()  # runs once when the server starts, creates the table if needed
 
 
class SubscribeRequest(BaseModel):
    email: EmailStr

@app.get("/")
def home():
    return {"message": "Hello, this is my news API"}
  
@app.get("/news") #endpoint
def get_news(category: str = None):
    articles = the_news() 
    if category:
        articles = [a for a in articles if a["category"] == category] 
    return articles

@app.post("/subscribe")
def subscribe(request: SubscribeRequest):
    added = add_subscriber(request.email)
    if not added:
        raise HTTPException(status_code=400, detail="Email is already subscribed")
    
    return {
        "message": f"{request.email} subscribed successfully",
        "total_subscribers": subscriber_count()
    }