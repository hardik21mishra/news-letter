from fastapi import FastAPI
from app import the_news
 
app = FastAPI()

@app.get("/")
def home():
    return {"message": "Hello, this is my news API!"}
  
@app.get("/news")
def get_news(category: str = None):
    articles = the_news()
 
    if category:
        articles = [a for a in articles if a["category"] == category]
 
    return articles
 