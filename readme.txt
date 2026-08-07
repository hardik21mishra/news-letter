# 📰 Automated Tech Newsletter

An end-to-end backend system that automatically collects technical news from trusted sources, summarizes it using an LLM, allows a human curator to select the best articles through Google Sheets, and delivers a curated newsletter to subscribers.
The goal of this project is not to simply aggregate news, but to build a scalable newsletter platform where quality content is curated, categorized, and delivered to the right audience.

---

Features

- Fetches articles from multiple technical RSS feeds
- Cleans and normalizes article content
- Generates concise summaries using the Groq API (Llama 3.1)
- Automatically categorizes articles (using RSS categories when available, otherwise using the LLM)
- Stores articles in a MySQL database
- Exports articles to Google Sheets for manual curation
- Imports curator selections back into the database
- Supports weekly picks such as:
  - Tech of the Week
  - Paper of the Week
  - Topic of the Week
- Stores subscriber information in MySQL
- Sends curated newsletters via email
- REST API built with FastAPI for subscriber management and newsletter operations

---

Project Workflow

                 RSS Feeds
                     │
                     ▼
          Fetch & Clean Articles
                     │
                     ▼
         Generate Summary (Groq)
                     │
      RSS Category? ────────────────┐
             │                      │
            Yes                    No
             │                      │
             ▼                      ▼
      Keep Category       Generate Category (Groq)
             │                      │
             └──────────────┬───────┘
                            ▼
                    Store in MySQL
                            │
                            ▼
              Export to Google Sheets
                            │
                            ▼
                Human Curator Reviews
                            │
                            ▼
            Import Selected Articles
                            │
                            ▼
              Build Newsletter Sections
                            │
                            ▼
             Send to Subscribers

Tech Stack

# Backend
- Python
- FastAPI

# Database
- MySQL

# LLM
- Groq API
- Llama 3.1 8B Instant

# Data Sources
- RSS Feeds

# Integrations
- Google Sheets API
- Gmail SMTP

Project Structure

newsletter/
│
├── app.py                  # Fetches articles from RSS feeds
├── categorize.py           # Generates summaries and categories
├── db.py                   # Database operations
├── google_sheets.py        # Export articles to Google Sheets
├── import_marks_store.py   # Import curator selections from google sheets
├── send_email.py           # Builds newsletter
├── mailer.py               # Sends emails
├── main.py                 # FastAPI application
└── requirements.txt

## Database

The project currently uses three primary tables:

### Articles
Stores every fetched article along with its metadata.

- Title
- Description
- Source
- URL
- Published Date
- Summary
- Category

### Subscribers

Stores newsletter subscribers.

- Name
- Email
- Contact Number
- Interests
- Active Status

### Selections

Stores curator-approved articles for each newsletter edition.

- Article ID
- Mark Type
- Week
- Created At

---

## Newsletter Curation

Instead of publishing every fetched article, the project introduces a human review step.

Articles are exported to a Google Sheet where the curator can mark them as:

- Keep
- Tech of the Week
- Paper of the Week
- Topic of the Week

These selections are imported back into the database and used to generate the final newsletter.

This approach combines AI automation with human editorial judgment.

---

## API Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/subscribe` | Add a subscriber |
| POST | `/send_email` | Send a newsletter to a custom list of email addresses |
| GET | `/news` | Build and send the weekly newsletter to all subscribers |