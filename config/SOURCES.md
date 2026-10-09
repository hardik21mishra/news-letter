# Newsletter fetching settings

Edit `sources.json` to tune discovery and the curator's workload. Keep normal RSS
URL/name mappings in `feeds.json` and Medium RSS mappings in `medium_feeds.json`.
The eight existing Medium tag feeds have their own pool, separate from the 40 normal
RSS feeds. All three new APIs work without API keys: **no `.env` changes,
paid plans, or new Python dependencies are needed**. Existing Groq, database, Google,
and publishing credentials continue to work as before.

## Curator workload and selection

`selection.max_articles` is an adjustable ceiling shared by fetching and Google Sheet
export. The default is 60, not a quota or minimum. Lower it for a shorter review session
or raise it to see more candidates. The exporter still uses today's summarized database
rows, newest first; it now uses this same ceiling even after several runs in a day.
Repeated runs may therefore mix shortlists from earlier in the day.

Selection takes turns across normal RSS, GitHub, arXiv, Hacker News, and Medium, deduplicating against
the articles already selected. `selection.max_articles_per_source` (default 12) caps
each of these five groups. Normal RSS and Medium each have a separate allowance of 12;
Medium never consumes the normal RSS allowance. Unfilled slots are not transferred
to another source. For example, 12 normal RSS + 12 Medium + 12 HN + 12 arXiv + 2 releases
gives 50 articles. With all six configured projects releasing, the current defaults
can yield 54; the overall ceiling is 60. This is a ceiling, not a required quota:
relevance, publication dates, and publisher limits still apply. Preview prints both
candidate counts and the final `Shortlist mix`.

RSS favors newer publication days, useful descriptions (at least 160
characters), then publication time. HN retains its community ranking. GitHub follows
your project-list order and picks recent stable releases; arXiv keeps newest matching
submissions. `selection.max_rss_articles_per_publisher` (default 3) prevents one normal
RSS publisher from dominating that pool. Medium is governed by its separate source
allowance rather than the normal RSS publisher cap, so it can contribute up to 12.
Its topic feeds take turns supplying candidates, and duplicates across topics or any
other source are removed. Articles still use `source: "Medium"` downstream.

This is simple metadata-based selection, not a guarantee of editorial importance.
The curator remains the final judge. There is no filler to meet a count.

## Source controls

Every source has `enabled`, `max_articles`, `max_age_days`, and `time_budget_seconds`.
`max_articles` limits that source's eligible candidates before the final shortlist.
Use `enabled: false` to disable it. Use nonnegative integer article counts and positive
timeout values. A keyword list of `[]` turns off that source's keyword filter.

| Source | Defaults and tuning |
| --- | --- |
| RSS | Inspect `entries_per_feed: 15`; keep at most `max_articles_per_feed: 4`; retain at most 80 candidates. Feeds take turns when filling the candidate pool, so the first busy feed cannot consume it. |
| Medium RSS | Uses `medium_feeds.json` and its own `medium` settings. Inspect 15 entries per feed; keep at most 4 per feed and 40 candidates total, with a separate 45-second budget. Up to 12 can reach the final shortlist independently of normal RSS. |
| Hacker News | Inspect the top 80 IDs (`max_items_to_check`); require `min_score: 30`, a matching technical `keywords` term, and an external HTTP(S) link; retain at most 20 candidates for selection. Excludes deleted/dead items, jobs, polls, and text-only threads. |
| GitHub | One releases-list request per project, inspecting `releases_per_project: 5`; keep at most `max_articles_per_project: 1`, 6 total. Drafts and prereleases are excluded. |
| arXiv | One request for up to `max_results: 80`, restricted to `categories` (`cs.AI`, `cs.LG`, `cs.CL`) and recent submission dates, then a local title/abstract `keywords` filter; retain at most 20 candidates for selection. |

To change GitHub projects, edit `github.projects` using public `owner/repository` names:

```json
"projects": ["astral-sh/uv", "rust-lang/rust", "kubernetes/kubernetes",
             "pytorch/pytorch", "huggingface/transformers", "ollama/ollama"]
```

Keep this list small and ordered by your interests. A project must publish GitHub
**Releases**; Git tags alone do not appear in this API. The unauthenticated GitHub API
allows 60 requests/hour per originating IP, shared with other unauthenticated users on
that IP. A 403/429 logs a warning and ends GitHub fetching for that run; other sources
continue. No token is requested or read.

`network` sets connect/read timeouts, a request time budget, response-size limits, and
a description-length limit (6,000 characters) to keep Groq input modest. Descriptions
preserve apostrophes, URLs, and technical notation when HTML and excess whitespace
are removed. RSS overrides the default
3 MB response limit with `rss.max_response_bytes: 15000000` (15 MB), because Istio and
Project Zero publish large full-content feeds. The other APIs retain the 3 MB limit.
Meta AI uses its AI Research category feed, and Project Zero uses its current
`projectzero.google/feed.xml` feed.

There are no automatic retries. Five source workers use separate HTTP sessions. Budget checks occur
between requests and response chunks; socket reads still rely on the read timeout, so
these budgets are best-effort rather than process-level hard deadlines. Completed
articles survive a later failure. Warnings identify the source/feed/item that failed.

## Dates, links, and limitations

- Articles retain exactly `title`, `source`, `description`, `published_at`, `link`,
  `summary`, and `category`. Dates remain naive IST datetimes for the existing cleaner
  and MySQL. `summary` remains `None` until Groq runs.
- Missing, invalid, future, and old publication dates are excluded. `max_age_days: 2`
  uses the same IST calendar-day cutoff as the existing cleaner. Increasing a fetching
  age limit alone does not bypass the cleaner's existing two-day window.
- Deduplication uses URL keys with tracking parameters/fragments removed, normalized
  host/scheme/trailing slash/query order, plus whitespace/case-normalized titles.
  Meaningful query parameters remain. arXiv abstract/PDF/version URLs share a key.
  Original article links are retained in output. The first selected occurrence wins;
  a candidate excluded by a source/publisher cap does not suppress another source's
  eligible occurrence. Redirects/short URLs and differently titled
  syndications are not resolved or compared semantically. Deduplication is per run.
- HN timestamps describe submission to HN, not the publisher's publication time. Link
  stories usually have no abstract: their description explicitly says so and includes
  the title and community metadata. Groq therefore has less context for those stories.
- arXiv uses original publication/submission dates, not revision dates. It fetches only
  metadata/abstracts, never PDFs. Quiet days, posting delays, strict filters, outages, or
  Groq failures can mean fewer articles reach the sheet. Avoid rapid repeated runs:
  arXiv requires at most one request every three seconds and recommends one daily
  request for an unchanged query. Each run makes at most one arXiv request; there is no
  persistent cache or cross-process rate limiter.

Official references: [Hacker News API](https://github.com/HackerNews/API),
[GitHub releases](https://docs.github.com/en/rest/releases/releases),
[GitHub rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api),
[arXiv API](https://info.arxiv.org/help/api/user-manual.html),
[arXiv API terms](https://info.arxiv.org/help/api/tou.html).

To fetch real articles and print all their fields in the terminal, run from the
repository root:

```powershell
venv\Scripts\python.exe fetch_news.py --preview
```

This displays source counts, failure warnings, and the selected articles as formatted
JSON. It contacts the news sources only; it does not call Groq, use the database, update
Sheets, or send anything. Without `--preview`, `fetch_news.py` retains its original
fetch/clean/summarize/save behavior.

Run offline verification from the repository root:

```powershell
venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests mock HTTP responses, database connections, and sheet writes. They do not run a
pipeline, call Groq, send messages, or publish anything.
