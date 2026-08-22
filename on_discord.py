import os
import requests
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def publish_to_discord(article):
    if not DISCORD_WEBHOOK_URL:
        print("WARNING: DISCORD_WEBHOOK_URL not set.")
        return False

    title = article.get("title", "Title not available")
    source = article.get("source", "NA")
    date = article.get("published_at", "NA")
    summary = article.get("summary", "")
    url = article.get("url", "")
    category = article.get("category", "Tech News")

    message = {
        "embeds": [
            {
                "title": title,
                "description": summary,
                "url": url,
                "fields": [
                    {
                        "name": "Source",
                        "value": source,
                        "inline": True
                    },
                    {
                        "name": "Date",
                        "value": str(date),
                        "inline": True
                    },
                    {
                        "name": "Category",
                        "value": category,
                        "inline": True
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=message,
            timeout=30,
        )
    except requests.RequestException as error:
        print(f"Failed to publish '{title}' to Discord: {error}")
        return False

    print("Discord response:", response.status_code)
    print("Discord response body:", response.text)

    if response.status_code not in (200, 204):
        print(f"Failed to publish '{title}' to Discord")
        return False

    print(f"Published to Discord: {title}")
    return True
