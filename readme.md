# Automated Tech Newsletter

This project is a Python-based newsletter system that collects technical news from RSS feeds, processes the articles, and prepares a newsletter for subscribers.
The main focus is on AI, software development, cloud, infrastructure, and other technology-related topics. Articles are collected automatically, but the final selection is still reviewed manually through Google Sheets.

## How it works

The project is split into two main pipelines.

```text
RSS feeds
   |
   v
Fetch and clean articles
   |
   v
Summarize and categorize with Groq
   |
   v
Store articles in MySQL
   |
   v
Send articles to Google Sheets
   |
   v
Curator reviews and marks articles
   |
   v
Import the selections into MySQL
   |
   v
Build and send the newsletter
```

### Pipeline 1 — Fetch and prepare articles

Run:

```bash
python run_pipeline1.py
```

This pipeline does the following:

1. Creates the required MySQL tables if they don't already exist.
2. Fetches the two latest articles from each RSS feed.
3. Cleans the article data and normalizes the dates.
4. Uses Groq to generate summaries and categories where needed.
5. Saves the processed articles in the `articles` table.
6. Updates the first tab of the configured Google Sheet with the articles ready for review.

The Google Sheet also contains a `Mark` column, which is used by the curator to select articles for the newsletter.

### Curator review

Once Pipeline 1 has finished, open the Google Sheet and review the articles.

The following values can be entered in the `Mark` column:

- `Keep` or `keep` — include the article in the regular news section.
- `tech_of_week` — select the Tech of the Week article.
- `topic_of_week` — select the Topic of the Week article.

The importer also checks the weekly categories and warns if there is no selection or if more than one article has been selected for the same weekly category.

### Pipeline 2 — Import selections and send

Run:

```bash
python run_pipeline2.py
```

This pipeline:

1. Reads the marks from the Google Sheet.
2. Saves the selected articles in the MySQL `selections` table.
3. Builds the newsletter using those selections.
4. Sends the newsletter to active subscribers through Gmail SMTP.

## FastAPI

The project also includes a small FastAPI application for operations that are useful outside the two main pipelines.

Start it with:

```bash
python main.py
```

Or run it directly with Uvicorn:

```bash
uvicorn main:app --reload
```

By default, the API runs at:

```text
http://127.0.0.1:8000
```

FastAPI's interactive documentation is available at:

```text
http://127.0.0.1:8000/docs
```

### Available endpoints

| Method | Endpoint | What it does |
| --- | --- | --- |
| GET | `/` | Returns a simple welcome message. |
| GET | `/news` | Returns articles marked as regular `news`. |
| POST | `/subscribe` | Adds a new subscriber. |
| GET | `/unsubscribe/{user_id}` | Deactivates a subscriber. |
| POST | `/broadcast` | Sends the newsletter immediately or schedules it. |
| POST | `/send-email` | Sends the newsletter to specific email addresses immediately or schedules it. |
| GET | `/get_sheet` | Downloads the current Google Sheet as an Excel file. |

For example, to download the curator sheet locally:

```text
http://127.0.0.1:8000/get_sheet
```

### Subscribe request

```json
{
  "email": "reader@example.com",
  "name": "Reader",
  "contact_no": "1234567890",
  "interests": ["ai", "cloud"]
}
```

### Scheduled broadcast

```json
{
  "send_at": "2026-08-21T09:00:00+05:30"
}
```

## Setup

### 1. Create a virtual environment

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install the dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root.

Do not commit this file to Git.

```dotenv
# MySQL
MYSQL_HOST=your-mysql-host
MYSQL_PORT=3306
MYSQL_USER=your-mysql-user
MYSQL_PASSWORD=your-mysql-password
MYSQL_DATABASE=your-database

# Optional MySQL TLS settings
MYSQL_SSL_CA=path-to-ca-certificate
MYSQL_SSL_VERIFY_CERT=true

# Google Sheets
GOOGLE_SHEET_ID=your-google-sheet-id

# Email
SENDER_EMAIL=your-gmail-address
EMAIL_APP_PASSWORD=your-gmail-app-password

# Optional: public URL used in unsubscribe links
BASE_URL=http://127.0.0.1:8000

# Optional when credentials.json is not available
# GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account", ...}
```

### 4. Set up Google Sheets

The project uses a Google service account to access the sheet.

1. Create or select a project in Google Cloud.
2. Enable the Google Sheets API and Google Drive API.
3. Create a service account and download its JSON key.
4. Save the key as `credentials.json` in the project root when running locally.
5. Share the Google Sheet with the service account's email address.
6. Set `GOOGLE_SHEET_ID` to the ID from the Google Sheet URL.

The project currently works with the first tab of the spreadsheet.

For deployments where `credentials.json` is not available, the service-account JSON can be provided through the `GOOGLE_SERVICE_ACCOUNT_JSON` environment variable.

### 5. Set up Gmail

The email functionality uses Gmail SMTP.

You need to use a Gmail App Password for `EMAIL_APP_PASSWORD`. Your normal Gmail account password will not work for this SMTP login.

## Database

The database is initialized through `init_db()` in `db.py`.

The main tables are:

- `articles` — stores the articles, summaries, categories, and related timestamps.
- `selections` — stores the curator's article selections.
- `subscribers` — stores subscriber information and whether each subscriber is active.

## Project structure

```text
newsletter/
├── main.py                  # FastAPI app and API endpoints
├── fetch_news.py            # RSS fetching and pipeline entry point
├── data_cleaning.py         # Cleans and normalizes article data
├── categorize.py            # Generates summaries and categories with Groq
├── db.py                    # MySQL connection and database operations
├── google_sheets.py         # Google Sheets authentication and import/export
├── import_marks_store.py    # Imports curator marks into MySQL
├── send_email.py            # Builds newsletter content and broadcasts it
├── mailer.py                # Sends individual emails through Gmail SMTP
├── run_pipeline1.py         # Runs the fetching and Google Sheets pipeline
├── run_pipeline2.py         # Imports selections and sends the newsletter
├── requirements.txt         # Python dependencies
├── credentials.json         # Local Google service-account key (keep private)
└── README.md                # Project documentation
```