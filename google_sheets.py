"""
Replaces manual Excel file passing with a live Google Sheet, using your
service account credentials. Same Mark-column workflow as before -- the
curator just edits in a browser now instead of you emailing files back
and forth.

Needs:
    pip install gspread google-auth

Setup (one-time):
    1. Share your Google Sheet with the service account's email address
       (found inside the credentials JSON, field "client_email") --
       give it Editor access, or this won't be able to write to it.
    2. Set env vars (same pattern as everything else):
         GOOGLE_SHEET_ID              -- from the sheet's URL
         GOOGLE_SERVICE_ACCOUNT_JSON  -- the ENTIRE contents of the
                                         credentials JSON file, pasted as
                                         one string. NEVER commit the
                                         actual .json file to your repo --
                                         it's a real login, unlike ca.pem.
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
        SELECT id, title, description, published_at, url, summary
        FROM articles
        ORDER BY fetched_at DESC
        LIMIT %s
    """, (ARTICLE_LIMIT,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    sheet = get_sheet()
    sheet.clear()

    headers = ["ID", "Title", "Description", "Published_date", "Link", "Summary", "Mark"]
    data = [headers]
    for r in rows:
        data.append([
            r["id"], r["title"], r["description"] or "", r["published_at"] or "",
            r["url"] or "", r["summary"] or "", "",
        ])

    sheet.update(data)

    sheet.format(f"C2:C{len(data)}", {"wrapStrategy": "WRAP"})  # Description
    sheet.format(f"F2:F{len(data)}", {"wrapStrategy": "WRAP"})  # Summary

    print(f"Exported {len(rows)} articles to the Google Sheet")
    print("Curator can now edit it live at the sheet's URL -- no file passing needed.")


if __name__ == "__main__":
    export_articles_to_sheet()