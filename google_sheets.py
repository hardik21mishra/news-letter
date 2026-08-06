"""
Replaces manual Excel file passing with a live Google Sheet.
The curator just edits in a browser now instead of manually emailing files back
and forth.
"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import date
from db import get_connection, mark_article
# from fetch_news import fetch_sum_save

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID") 

# print("Using SHEET_ID:", repr(SHEET_ID))

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

ARTICLE_LIMIT = 200


def get_sheet():
    if os.path.exists("credentials.json"):
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    else:
        creds_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1  # first tab


def export_articles_to_sheet():
    """Overwrites the sheet with the latest fetched articles + empty Mark column."""

    # fetch_sum_save() # --> runs the fetch file before 

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT id, title, description, published_at, url, summary, category
        FROM articles
        ORDER BY fetched_at DESC
        LIMIT %s
    """, (ARTICLE_LIMIT,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    sheet = get_sheet()
    sheet.clear()

    headers = ["ID", "Title", "Category", "Description", "Published_date", "Link", "Summary", "Mark"]
    data = [headers]
    for r in rows:
        data.append([
            r["id"], 
            r["title"], 
            r["category"] or "",
            r["description"] or "", 
            r["published_at"] or "",
            r["url"] or "", 
            r["summary"] or "", 
            "",
        ])

    sheet.update(data)

    sheet.format(f"C2:C{len(data)}", {"wrapStrategy": "WRAP"})  # Description
    sheet.format(f"F2:F{len(data)}", {"wrapStrategy": "WRAP"})  # Summary
    sheet.format(f"G2:G{len(data)}", {"wrapStrategy": "WRAP"})  # Category

    print(f"Exported {len(rows)} articles to the Google Sheet")
    print("Curator can now edit it live at the sheet's URL -- no file passing needed.")


if __name__ == "__main__":
    export_articles_to_sheet()