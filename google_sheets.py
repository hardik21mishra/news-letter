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

VALID_MARKS = {"keep", "tech_of_week", "paper_of_week", "topic_of_week"}
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


def import_marks_from_sheet():
    """Reads the curator's current marks straight from the live sheet."""
    sheet = get_sheet()
    records = sheet.get_all_records()  # list of dicts, keyed by header row

    week_of = date.today().isoformat()
    counts = {"news": 0, "tech_of_week": 0, "paper_of_week": 0, "topic_of_week": 0}

    for row in records:
        article_id = row.get("ID")
        mark = str(row.get("Mark", "")).strip().lower()

        if not article_id or not mark:
            continue

        if mark not in VALID_MARKS:
            print(f"Skipping article {article_id}: unrecognized mark '{mark}'")
            continue

        mark_type = "news" if mark == "keep" else mark
        mark_article(article_id, mark_type, week_of)
        counts[mark_type] += 1

    print(f"\nImported marks for week_of={week_of}:")
    for mark_type, count in counts.items():
        print(f"  {mark_type}: {count}")

    for weekly_type in ["tech_of_week", "paper_of_week", "topic_of_week"]:
        if counts[weekly_type] == 0:
            print(f"WARNING: no article marked '{weekly_type}'")
        elif counts[weekly_type] > 1:
            print(f"WARNING: {counts[weekly_type]} articles marked '{weekly_type}', expected 1")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "import":
        import_marks_from_sheet()
    else:
        export_articles_to_sheet()