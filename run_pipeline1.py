from fetch_news import fetch_sum_save
from google_sheets import export_articles_to_sheet


def run_pipeline1():
    print("=" * 60)
    print("PIPELINE 1 STARTED")
    print("=" * 60)

    print("\n[1/2] Fetching, cleaning, summarizing and saving articles...")
    fetch_sum_save()

    print("\n[2/2] Exporting eligible articles to Google Sheets...")
    export_articles_to_sheet()

    print("\n" + "=" * 60)
    print("PIPELINE 1 COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline1()