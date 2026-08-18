from import_marks_store import import_marks_from_sheet
from send_email import build_newsletter_mails, send_to_all_subscribers

def run_pipeline2():
    print("-" * 60)
    print("PIPELINE 2 STARTED")
    print("-" * 60)

    print("\n[1/2] Importing curator marked content from Google Sheets...")
    import_marks_from_sheet()

    print("\n[2/2] Building and sending newsletter...")
    mails = build_newsletter_mails()

    if not mails:
        print("No newsletter content available. Nothing to send.")
        return

    for subject, body, html_email in mails:
        send_to_all_subscribers(subject, body, html_email)

    print("\n" + "-" * 60)
    print("PIPELINE 2 COMPLETED SUCCESSFULLY")
    print("-" * 60)

if __name__ == "__main__":
    run_pipeline2()