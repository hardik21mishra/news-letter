from import_marks_store import import_marks_from_sheet
from on_discord import publish_to_discord
from on_telegram import publish_to_telegram
from db import get_selected_articles
from send_email import BASE_URL, build_newsletter_mails, send_to_all_subscribers

def run_pipeline2():
    print("-" * 60)
    print("PIPELINE 2 STARTED")
    print("-" * 60)

    print("\n[1/2] Importing curator marked content from Google Sheets...")
    import_marks_from_sheet()

    print("\n[2/2] Building and sending newsletter to all platforms...")
    selected_articles = get_selected_articles()
    mails = build_newsletter_mails(selected_articles)

    if mails:
        for subject, body, html_email in mails:
            send_to_all_subscribers(subject, body, html_email)
    else:
        print("No email newsletter content available.")

    for article in selected_articles:
        article = dict(article)
        if BASE_URL and article.get("id"):
            article["url"] = f"{BASE_URL}/track/0/{article['id']}?platform=telegram"
        publish_to_telegram(article)

    for article in selected_articles:
        article = dict(article)
        if BASE_URL and article.get("id"):
            article["url"] = f"{BASE_URL}/track/0/{article['id']}?platform=discord"
        publish_to_discord(article)

    print("\n" + "-" * 60)
    print("PIPELINE 2 COMPLETED SUCCESSFULLY")
    print("-" * 60)

if __name__ == "__main__":
    run_pipeline2()