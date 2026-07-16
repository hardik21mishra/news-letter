import requests
from app import the_news
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")
message = the_news()

# print(TOKEN)
# print(chat_id)

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

for article in message:
    text = (
        article["title"] + "\n\n"
        + article["summary"] + "\n\n"
        + "Published: " + article["published_date"] + "\n\n"
        + "Read full Article: " + article["link"]
    )
    print(requests.post(url, data={"chat_id": chat_id, "text": text}).json())