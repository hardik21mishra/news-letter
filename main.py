from fastapi import FastAPI
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone
from typing import List, Optional
from send_email import (
    BASE_URL,
    build_newsletter_mails,
    render_email_body,
    send_to_all_subscribers,
)
from apscheduler.schedulers.background import BackgroundScheduler
from mailer import send_single_email
from on_discord import publish_to_discord
from on_telegram import publish_to_telegram
from db import (
    add_subscriber,
    get_marked_articles,
    get_subscriber_id_by_email,
    track_newsletter_click,
    unsubscribe_subscriber,
    get_selected_articles,
    get_connection,
)
from google_sheets import download_sheet_xlsx, get_sheet_id
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    platforms: List[str] = ["email", "telegram", "discord"]

@app.get("/")
def home():
    return {"message": "Helloooo, this is my news API"}

@app.get("/analytics/overview")
def analytics_overview(platform: str = "all"):
    platform = platform.lower()

    if platform not in {"all", "email", "telegram", "discord"}:
        return {"error": "Invalid platform"}

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        # ---------------------------------------------------------
        # CATEGORY ANALYTICS
        # ---------------------------------------------------------
        if platform == "all":
            cur.execute("""
                SELECT
                    interest,
                    SUM(click_count) AS clicks
                FROM analytics
                GROUP BY interest
                ORDER BY clicks DESC
            """)
        else:
            cur.execute("""
                SELECT
                    interest,
                    SUM(click_count) AS clicks
                FROM analytics
                WHERE LOWER(platform) = %s
                GROUP BY interest
                ORDER BY clicks DESC
            """, (platform,))

        category_rows = cur.fetchall()

        category_distribution = [
            {
                "interest": row["interest"],
                "clicks": int(row["clicks"] or 0)
            }
            for row in category_rows
        ]

        most_popular = None

        if category_distribution:
            most_popular = category_distribution[0]

        # ---------------------------------------------------------
        # TELEGRAM / DISCORD
        # ---------------------------------------------------------
        # These are channel-level analytics.
        # Individual subscriber analytics are not relevant here.
        if platform in {"telegram", "discord"}:
            return {
                "platform": platform,
                "category_distribution": category_distribution,
                "most_popular": most_popular,
                "subscribers": []
            }

        # ---------------------------------------------------------
        # EMAIL / ALL
        # ---------------------------------------------------------
        cur.execute("""
            SELECT
                id,
                name,
                email,
                interests
            FROM subscribers
            WHERE active = TRUE
            ORDER BY id
        """)

        subscribers = cur.fetchall()

        subscriber_insights = []

        for subscriber in subscribers:

            if platform == "all":
                cur.execute("""
                    SELECT
                        interest,
                        platform,
                        click_count,
                        last_clicked_at
                    FROM analytics
                    WHERE subscriber_id = %s
                    ORDER BY click_count DESC
                """, (subscriber["id"],))

            else:
                cur.execute("""
                    SELECT
                        interest,
                        platform,
                        click_count,
                        last_clicked_at
                    FROM analytics
                    WHERE subscriber_id = %s
                      AND LOWER(platform) = %s
                    ORDER BY click_count DESC
                """, (subscriber["id"], platform))

            activity = cur.fetchall()

            total_clicks = sum(
                int(row["click_count"] or 0)
                for row in activity
            )

            strongest_interest = None

            if activity:
                strongest_interest = {
                    "interest": activity[0]["interest"],
                    "clicks": int(activity[0]["click_count"] or 0)
                }

            platform_clicks = {
                "email": 0,
                "telegram": 0,
                "discord": 0
            }

            for row in activity:
                row_platform = str(row["platform"]).lower()

                if row_platform in platform_clicks:
                    platform_clicks[row_platform] += int(
                        row["click_count"] or 0
                    )

            subscriber_insights.append({
                "id": subscriber["id"],
                "name": subscriber["name"],
                "email": subscriber["email"],
                "declared_interests": subscriber["interests"],
                "total_clicks": total_clicks,
                "strongest_interest": strongest_interest,
                "platform_clicks": platform_clicks,
                "activity": activity
            })

        return {
            "platform": platform,
            "category_distribution": category_distribution,
            "most_popular": most_popular,
            "subscribers": subscriber_insights
        }

    finally:
        cur.close()
        conn.close()

@app.get("/subscribers")
def get_subscribers():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT
                id,
                name,
                email,
                contact_no,
                interests,
                subscribed_at,
                active
            FROM subscribers
            ORDER BY id DESC
        """)

        return cur.fetchall()

    finally:
        cur.close()
        conn.close()
  
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
def track_click(subscriber_id: int, article_id: int, platform: str = "email"):
    article_url = track_newsletter_click(subscriber_id, article_id, platform)
    if not article_url:
        return Response(content="Subscriber or article not found", status_code=404)

    return RedirectResponse(url=article_url, status_code=307)

def broadcast_now(platforms=None):
    platforms = platforms or ["email", "telegram", "discord"]
    selected_articles = get_selected_articles()
    results = []
    if "email" in platforms:
        for subject, body, html_email in build_newsletter_mails(selected_articles):
            send_to_all_subscribers(subject, body, html_email)
            results.append({"platform": "email", "subject": subject, "sent": True})
    for platform, sender in (
        ("telegram", publish_to_telegram),
        ("discord", publish_to_discord),
    ):
        if platform not in platforms:
            continue
        sent = 0
        for selected_article in selected_articles:
            article = dict(selected_article)
            article_id = article.get("id")
            if BASE_URL and article_id:
                article["url"] = f"{BASE_URL}/track/0/{article_id}?platform={platform}"
            sent += sender(article)
        results.append({"platform": platform, "sent": sent, "total": len(selected_articles)})
    return results

@app.post("/broadcast")
def broadcast_endpoint(request: BroadcastRequest):
    now = datetime.now(timezone.utc)
    send_at = request.send_at
    if send_at is not None and send_at.tzinfo is None:
        send_at = send_at.replace(tzinfo=timezone.utc)
    if send_at is None or send_at <= now:
        results = broadcast_now(request.platforms)
        return {
            "message": "Newsletter broadcast send immediately", "results": results
        }
    else:
        scheduler.add_job(broadcast_now, "date", run_date=send_at, args=[request.platforms])
        return {"message": f"Newsletter broadcast scheduled for {send_at.isoformat()}"}

def send_on_demand(emails):
    results = []
    selected_articles = get_selected_articles()
    for email in emails:
        subscriber_id = get_subscriber_id_by_email(email)
        for subject, body, html_email in build_newsletter_mails(selected_articles):
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