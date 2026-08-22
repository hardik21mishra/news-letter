import os

import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def publish_to_telegram(article):
	if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
		print("WARNING: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set.")
		return False

	title = article.get("title", "Title not available")
	summary = article.get("summary", "")
	url = article.get("url") or article.get("link", "")
	message = f"{title}\n\n{summary}\n\nRead full article: {url}"

	try:
		response = requests.post(
			f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
			data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
			timeout=30,
		)
	except requests.RequestException as error:
		print(f"Failed to publish '{title}' to Telegram: {error}")
		return False
	if not response.ok:
		print(f"Failed to publish '{title}' to Telegram: {response.text}")
		return False

	print(f"Published to Telegram: {title}")
	return True