from datetime import date
from db import mark_article
from google_sheets import get_sheet
from db import clear_selections

VALID_MARKS = {"Keep", "keep", "tech_of_week", "paper_of_week", "topic_of_week"}

def import_marks_from_sheet():
    """Reads the curator's current marks straight from the live sheet."""
    sheet = get_sheet()
    records = sheet.get_all_records()  # list of dicts, keyed by header row

    week_of = date.today().isoformat()
    counts = {"news": 0, "tech_of_week": 0, "paper_of_week": 0, "topic_of_week": 0}

# Remove this week's previous selections
    clear_selections(week_of)

    for row in records:
        article_id = row.get("ID")
        mark = str(row.get("Mark", "")).strip().lower()

        if not article_id or not mark:
            continue

        if mark not in VALID_MARKS:
            print(f"Skipping article {article_id}: unrecognized mark '{mark}'")
            continue

        mark_type = "news" if mark == "keep" or mark == "Keep" else mark
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

import_marks_from_sheet()