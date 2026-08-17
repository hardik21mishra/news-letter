# Replace manual excel file editing with live google sheet
# Now no need to manually upload and download the google sheet
# to send and receive from the curator

import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
from db import get_connection
# from fetch_news import fetch_sum_save

from dotenv import load_dotenv
load_dotenv()

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID") 

# print("Using SHEET_ID:", repr(SHEET_ID))

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

ARTICLE_LIMIT = 200
IST = ZoneInfo("Asia/Kolkata")

def get_sheet():
    if os.path.exists("credentials.json"):
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    else:
        creds_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1  # first tab

def export_articles_to_sheet():
    """Overwrites the sheet with today's fetched articles + empty Mark column."""

    # fetch_sum_save() # --> runs the fetch file before 

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    today = datetime.now(IST).date()
    cutoff_date = today - timedelta(days=2)

    cur.execute("""
        SELECT id, title, source, description, published_at, url, summary, category
        FROM articles
        WHERE DATE(fetched_at) = %s AND DATE(published_at) >= %s
        ORDER BY published_at DESC
        LIMIT %s
    """, (today, cutoff_date, ARTICLE_LIMIT))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    sheet = get_sheet()
    sheet.clear()
    headers = ["ID", "Title", "source", "Category", "Description", "Published_at", "Link", "Summary", "Mark"]
    data = [headers]
    for r in rows:
        data.append([
            r["id"], 
            r["title"], 
            r["source"],
            r["category"] or "",
            r["description"] or "", 
            r["published_at"].strftime("%Y-%m-%d %H:%M:%S") if r["published_at"] else "",
            r["url"] or "", 
            r["summary"] or "", 
            "",
        ])
    sheet.update(data)
    
    # Wrap long text so it stays inside its own cell
    sheet.format(f"D2:D{len(data)}", {
        "wrapStrategy": "WRAP",
        "verticalAlignment": "TOP"
    })

    sheet.format(f"G2:G{len(data)}", {
        "wrapStrategy": "WRAP",
        "verticalAlignment": "TOP"
    })

    sheet.format(f"C2:C{len(data)}", {
        "wrapStrategy": "WRAP",
        "verticalAlignment": "TOP"
    })

    print(f"Exported {len(rows)} articles to the Google Sheet")
    print("Curator can now edit it live at the sheet's URL -- no file passing needed.")

if __name__ == "__main__":
    export_articles_to_sheet()
