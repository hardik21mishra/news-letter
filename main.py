from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from app import the_news

app = FastAPI()

SUBSCRIBERS_FILE = "subscribers.txt"
 
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
    email = request.email
 
    existing = []
    with open(SUBSCRIBERS_FILE, "r") as f:
        existing = [line.strip() for line in f.readlines() if line.strip()]
    
    if email in existing:
        raise HTTPException(status_code=400, detail="Email is already subscribed")
 
    with open(SUBSCRIBERS_FILE, "a") as f:
        f.write(email + "\n")
 
    return {f"{email} subscribed successfully"}