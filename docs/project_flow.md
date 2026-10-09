# Project flow and maintenance

## What the project does

The project collects technology articles, asks an AI model to summarize them, lets a person choose articles in Google Sheets, and publishes those choices. MySQL is the shared storage used by both pipelines and the API.

```text
config/feeds.json
    -> fetch_news.py
    -> data_cleaning.py
    -> categorize.py
    -> db.py: articles table
    -> google_sheets.py: curator sheet
    -> human review in the Mark column
    -> import_marks_store.py
    -> db.py: selections table
    -> send_email.py + templates/email/: email
    -> on_telegram.py: Telegram
    -> on_discord.py: Discord
```

A Python function groups a task under a name. An import makes another file's functions or values available. The `if __name__ == "__main__":` blocks run when you start that file directly. The pipeline files import the needed functions and call them in sequence.

## Pipeline 1: collect and prepare

Run `python run_pipeline1.py`.

1. `run_pipeline1.py` calls `fetch_sum_save()` in `fetch_news.py`.
2. `db.init_db()` creates missing tables. It does not migrate existing tables.
3. `fetch_news()` reads each configured RSS feed in order and takes its first two entries. It cleans text and converts available publication dates to Asia/Kolkata, removing timezone information for MySQL storage. Articles are dictionaries containing fields such as `title`, `link`, `description`, `published_at`, and `category`.
4. `data_cleaning.clean_articles()` removes undated articles, filters by the existing two-day calendar-date cutoff, sorts newest first, and removes duplicate titles.
5. `categorize.process_news()` uses Groq to request a summary for every remaining article. It also requests a category when the feed category is absent or in the existing generic-category set. The model, prompts, parsing, and temperature remain unchanged.
6. `db.save_articles()` inserts articles or updates an existing row with the same URL. It accepts the fetched `link` field and stores it in the database's `url` column.
7. `google_sheets.export_articles_to_sheet()` clears and rewrites the first sheet tab with up to 200 articles fetched today in Asia/Kolkata that have a nonempty summary. It adds an empty `Mark` column for review.

## Pipeline 2: publish selected articles

Run `python run_pipeline2.py` after reviewing the sheet.

1. `import_marks_store.import_marks_from_sheet()` reads `ID` and `Mark`, accepting `keep`, `tech_of_week`, and `topic_of_week` after trimming and lowercasing. `keep` becomes the database mark `news`.
2. `db.mark_article()` inserts each selection. The same article/mark pair is unique, so importing that pair again does not create or update a selection.
3. `db.get_selected_articles()` retrieves selections created on the current UTC date, ordered by publication time and fetch time.
4. `send_email.build_newsletter_mails()` prepares the daily HTML newsletter and, when present, one plain-text email for the first Tech of the Week pick and one for the first Topic of the Week pick.
5. `send_to_all_subscribers()` retrieves active subscribers, fills the templates, uses Premailer to inline CSS, and sends each email through Gmail SMTP. Tracking and unsubscribe links are personalized as before.
6. The pipeline publishes each selected article to Telegram, then each selected article to Discord, using their platform-specific tracking URLs.

The main newsletter displays selected regular news. A `HISTORY` category is used for its history block. The weekly emails use the selected article's description, while regular news uses its summary.

## API and supporting files

| File | Responsibility |
| --- | --- |
| `main.py` | FastAPI routes for news, subscriptions, sending, scheduling, tracking, analytics, and Google Sheet access. |
| `db.py` | Connections, table creation, saving articles/selections/subscribers, and click analytics. |
| `mailer.py` | Sends an individual email for the API's on-demand email route. |
| `send_email.py` | Builds newsletter bodies and sends to active subscribers. |
| `google_sheets.py` | Authenticates to Google Sheets, exports articles, and downloads the sheet. |
| `on_telegram.py`, `on_discord.py` | Format article messages and call the respective platform APIs. |
| `.github/workflows/pipeline1.yml`, `pipeline2.yml` | Install dependencies and run the corresponding pipeline on manual or repository dispatch. |
| `requirements.txt` | Packages the application depends on. |
| `testing.ipynb` | A small separate FastAPI experiment; neither pipeline imports it. |
| `archive/` | Older implementations, including other fetchers and spreadsheet utilities; neither active pipeline imports them. |

`main.py` can send or schedule existing selections without importing the current Google Sheet marks. Scheduled jobs live in the API process's scheduler. Clicking a tracking link records category interest and redirects to the article. Subscription interests are stored and updated, but the current broadcast sends the same selected articles to all active subscribers.

## What belongs in which file

Hardcoding means writing a value directly in source code. This is normal for stable program rules. Separating content that you edit regularly makes maintenance easier; moving every number and string would add complexity without necessarily helping.

| Kind of value | Location in this project |
| --- | --- |
| RSS URLs and display names | `config/feeds.json` |
| Email layout, CSS, greeting, and body wording | `templates/email/` |
| Passwords, API keys, database connection settings | Existing environment variables or local `.env` |
| Google service-account credentials | Existing `credentials.json` or `GOOGLE_SERVICE_ACCOUNT_JSON` |
| Processing rules, prompts, limits, fallback values, subjects, and platform behavior | Their existing Python modules |

Only `fetch_news.py` and `send_email.py` needed executable-code changes for the feed/template extraction. Existing variable and function names remain available. All feed entries, template text, HTML whitespace, escaping, model settings, timezones, limits, email subjects, and sending order are preserved. The JSON and templates use Python's standard library; no new dependency was added.

## Existing behavior to consider separately

These observations came from the code review. They were deliberately left unchanged because fixing them would alter logic or output:

- In `categorize.py`, parsing `Category: AI` removes `Category` but leaves the colon, producing `: AI`.
- Weekly email builders read `pick.get('link', '')`, while selections from MySQL contain `url`. Consequently, database selections can produce a blank weekly email link.
- Both footer links, including **Manage Interests**, point to the unsubscribe URL.
- The default **On This Day** text is a fixed Apple Lisa statement. It is not selected according to the current date.
- Reimporting a previously selected article/mark pair leaves its original creation date unchanged. Since publication reads today's UTC selections, marking an older selection again does not make it eligible today.
- The Pipeline 2 GitHub Actions workflow does not map `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, or `DISCORD_WEBHOOK_URL` into its environment. The publishers skip sending when these variables are missing.

## Verification performed for this change

Compared the refactored modules with their original versions from Git, using a fixed clock and local sample data:

- 216 byte-for-byte HTML comparisons covering different platforms, subscriber IDs, base URLs, history records, missing fields, dates, Unicode, and HTML-special characters.
- 18 comparisons after real Premailer CSS processing.
- Plain-text weekly bodies, email subjects, email order, and selection of the first weekly pick.
- All 48 feed URLs, labels, and their order; mocked feed fetching produced the same 96 articles in both versions.
- Unaffected functions in both edited modules retained identical Python syntax trees.
- Resource loading from a different working directory and compilation of every active Python module.

These checks used no live database connections, feed downloads, Groq calls, or message delivery. Live service integration was not exercised. Premailer reported warnings about the existing CSS `transition` property in both versions; the CSS was preserved.

## Editor diagnostic corrections

`db.py` now describes the selected-article, subscriber-email, and click-query row shapes with type hints. The casts at database fetch boundaries tell the type checker which shape each existing query returns; they do not convert or change the returned data. The Aiven certificate checks are nested so the checker can see that a path exists before testing its contents. Connection settings and SQL remain unchanged.

`send_email.py` now explicitly types its mail list to accept both HTML-building functions and plain-text bodies. Sending with active subscribers and an unset `SENDER_EMAIL` or `EMAIL_APP_PASSWORD` raises a clear error before opening SMTP. This only changes the failure for missing credentials; configured sending and the existing no-subscriber return are preserved.

Both files passed Pyright in `standard` mode with zero errors and warnings. Comparisons against the versions before these diagnostic corrections covered 112 TLS/environment cases and identical SMTP calls, recipients, complete MIME messages, and sending order for the daily and weekly emails. SQL and other processing functions were also compared after removing type-only annotations. These checks used mocked database connections and SMTP delivery.
