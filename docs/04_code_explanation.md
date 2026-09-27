# 4. Code Explanation (A Simple Tour of the Code)

This page explains what each folder and important file does, in plain
words. You don't need to read actual code to understand this page.

## The big folders

```
src/            <- all the actual application code
  core/         <- settings, database connection, logging, shared tools
  ingestion/    <- the web scraper (reads SEC filings)
  models/       <- the database table definitions
  schemas/      <- the "shape" of data going in/out of the API
  analytics/    <- the math (ratios, growth, rankings)
  reporting/    <- chart drawing + PowerPoint building
  api/          <- the web server and its routes (URLs)
  dashboard/    <- the Streamlit webpage
alembic/        <- database version history (migrations)
scripts/        <- small command-line helper programs
tests/          <- automated tests that check the code works
docs/           <- you are here
```

---

## `src/core/` — the shared basics

- **`config.py`** — All the settings in one place (things like: how long to
  wait between requests, what the database address is, whether auth is
  turned on). Settings can be changed using environment variables or a
  `.env` file, without touching code.
- **`database.py`** — Sets up the connection to the database. There are
  **two** connections defined here: a normal ("sync") one used by the
  background Worker, and a faster ("async") one used by the web API. Both
  point to the same actual database.
- **`constants.py`** — Fixed values that don't change, like folder paths
  and the default browser identity string.
- **`celery_app.py`** — Sets up Celery (the background job system).
- **`logging_config.py`** — Makes all log messages come out as structured
  JSON, and tags every log line with a "request ID" so you can trace one
  user's request through the whole system.
- **`metrics.py`** — Defines the numbers we track for monitoring (how many
  scrapes succeeded/failed, how long report generation takes, cache
  hits/misses).
- **`cache.py`** — Small helper for saving/reading temporary data in Redis.
  If Redis isn't available, it fails quietly instead of crashing the app.

## `src/ingestion/` — the web scraper

This is the most "hands-on" part of the project — the part that actually
goes out and reads real webpages.

- **`sec_client.py`** — Talks to SEC's official, free lookup service to
  find a company's ID number (CIK) and its list of recent filings. Saves
  answers to disk temporarily (**caching**) so it doesn't ask the same
  question twice within a day.
- **`filing_discovery.py`** — A simple helper that asks `sec_client.py`:
  "give me this company's most recent filing" or "give me their last 4
  filings."
- **`browser.py`** — Controls the actual Chrome browser (via Playwright).
  Handles starting/closing the browser, and makes it look like a real
  person is browsing (realistic screen size, random small delays, hiding
  typical "this is a robot" signals).
- **`captcha_handler.py`** — Watches for "prove you're human" tests. If one
  appears, it stops safely instead of trying to cheat past it.
- **`parser.py`** — Reads the raw webpage code (HTML) and finds the tables
  that contain the Income Statement, Balance Sheet, and Cash Flow numbers.
- **`normalizer.py`** — Cleans up messy text numbers into real numbers.
  Example: turns `"$(2,345)"` into `-2345.0`, and `"$2.5 billion"` into
  `2500000000.0`.
- **`scraper.py`** — The "conductor" that uses all the above pieces
  together: open the filing page, find the tables, read them, clean the
  numbers, and repeat for several quarters of history.
- **`tasks.py`** — The actual Celery background job. This is what runs when
  someone clicks "ingest a company." It calls the scraper, then saves the
  results into the database (creating the Company, Period, and Line Item
  rows).

## `src/models/` — the database tables

Think of each file here as one drawer in a filing cabinet.

- **`company.py`** — The `Company` table: ticker, name, sector, exchange.
- **`financial.py`** — Three tables:
  - `FinancialPeriod` — one row per company per quarter (e.g. "AAPL, Q2
    2024").
  - `FinancialLineItem` — one row per number in that quarter (e.g.
    "Revenue = 94036").
  - `ComputedRatio` — one row per calculated ratio for that quarter (e.g.
    "net_margin = 0.21").
- **`report.py`** — The `ReportJob` table: tracks each PowerPoint report
  request and whether it's pending, processing, done, or failed.

## `src/schemas/` — the shape of data in and out

These files don't store anything — they just describe **what a valid
request or response looks like**. For example: "a request to create a
company must include a `ticker` (text) and a `name` (text)." FastAPI uses
these to automatically check incoming data and reject anything that
doesn't match, before it ever reaches your actual code.

## `src/analytics/` — the math, kept separate on purpose

- **`metrics.py`** — Pure math functions with no database or web code
  mixed in: growth rate, net margin, ROE, current ratio, and peer
  percentile ranking (how a company ranks compared to others, from 0 to
  100).

Keeping this file "pure" (no database, no web code) makes it very easy to
test — you just give it numbers and check the answer, nothing else needed.

## `src/api/` — the web server

- **`main.py`** — Starts the FastAPI app, wires together all the pieces
  (routes, security, logging, error handling, rate limiting, metrics).
- **`routers/companies.py`** — URLs for listing, creating, and viewing
  companies and their financials/ratios.
- **`routers/compare.py`** — The URL for comparing multiple companies
  against each other (peer comparison). Results are cached briefly.
- **`routers/reports.py`** — URLs for requesting a PowerPoint report,
  checking its status, and downloading it once ready.
- **`routers/ingestion.py`** — The URL for starting a scrape of a company.
- **`security.py`** — Checks the `X-API-Key` header on requests that change
  data.
- **`rate_limit.py`** — Limits how many times per minute someone can call
  the expensive endpoints (scraping, report generation).
- **`errors.py`** — Makes every error response (404 not found, 422 bad
  input, 429 too many requests, 500 server error) look the same shape, so
  anyone using the API always knows where to look for the error message.
- **`middleware.py`** — Gives every request a unique ID and logs how long
  each request took.

## `src/reporting/` — charts and PowerPoint

- **`charts.py`** — Draws 3 charts using Matplotlib: revenue/profit trend,
  margin trend, and peer comparison bar chart.
- **`pptx_builder.py`** — Builds the actual 4-slide PowerPoint file using
  python-pptx: a title slide, a KPI summary slide, a charts slide, and a
  peer benchmark slide.
- **`tasks.py`** — The Celery background job for building a report. It
  talks to the API (never the database directly) to get the data it needs,
  then builds the charts and the PowerPoint file.

## `src/dashboard/` — what the user actually sees

- **`app.py`** — The Streamlit dashboard page: pick a company, trigger a
  scrape, view KPI cards and charts, and download the finished report.
- **`api_client.py`** — A small helper that sends web requests to the API
  server. The dashboard is only allowed to talk to the API — never
  straight to the database.

## `alembic/` — database version history

- **`versions/001_initial_schema.py`** — The very first "version" of the
  database structure: it describes exactly which tables and columns should
  exist. If we ever need to add a new column later, we'd add a new
  "version" file here instead of just editing the database directly —
  this keeps a safe, trackable history of every database change.

## `scripts/` — command-line helpers

- **`run_pipeline.py`** — Lets you scrape one company from the terminal,
  without needing the full dashboard running.
- **`start_app.py`** — Starts both the API server and the dashboard
  together, for easy local testing.

## `tests/` — the safety net

Each `test_*.py` file checks one part of the system. For example:
`test_analytics.py` checks the ratio math is correct,
`test_ingestion.py` checks the scraper's database-saving logic,
`test_api.py` checks the web routes respond correctly,
`test_cache.py` checks caching works (and fails safely if Redis is down).

Together, these 70+ tests mean that if someone changes the code and
accidentally breaks something, the tests will fail and warn them —
**before** that broken code reaches real users.
