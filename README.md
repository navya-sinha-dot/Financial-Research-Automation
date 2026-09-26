# Financial Research Automation

Financial Research Automation (FRA) is an end-to-end pipeline that scrapes real
quarterly financial statements straight from **SEC EDGAR filings** using a live
Chromium browser, normalizes and stores the extracted figures, computes
financial ratios and peer benchmarks, and turns the result into an
investor-grade PowerPoint report — all served through a FastAPI backend and a
Streamlit dashboard.

There is no seeded, mocked, or synthetic financial data anywhere in the
running application. Every number in the database was extracted from a real
10-Q/10-K filing on `sec.gov`; if a scrape fails, the pipeline fails loudly
instead of silently substituting fake figures.

## Architecture

```mermaid
flowchart TD
    A[User enters a ticker] --> B[SEC company + CIK lookup]
    B --> C[SEC filing discovery: latest 10-Q / 10-K]
    C --> D[Playwright launches Chromium]
    D --> E[Filing page opened in the browser]
    E --> F[HTML tables located: income statement, balance sheet, cash flow]
    F --> G[Parser extracts raw statement rows]
    G --> H[Normalizer converts to numeric USD values]
    H --> I[(PostgreSQL / SQLite via SQLAlchemy)]
    I --> J[Pandas-based ratio engine: YoY, QoQ, margins, ROE, peer percentile]
    J --> K[FastAPI REST layer]
    K --> L[Streamlit dashboard]
    K --> M[Celery worker renders PPTX investor report]
```

## Why this stack

- **SEC EDGAR** is the official, free, public source of company financial
  statements — no paid market-data API keys required.
- **Playwright + Chromium** perform real browser automation against the live
  filing page, rather than an HTTP-only scrape, so the extraction is visible
  and demonstrable step by step.
- **FastAPI** is the only component allowed to touch the database; the
  dashboard and the Celery workers talk to it exclusively over HTTP. Routes
  run against an async SQLAlchemy engine (`asyncpg`/`aiosqlite`) so the API
  can serve concurrent requests without blocking on database I/O; Celery
  workers keep a separate synchronous engine, since a worker's execution
  model is inherently synchronous per process.
- **Celery + Redis** decouple slow work (a live browser scrape, a multi-slide
  PPTX render) from the request/response cycle.
- **Pandas** computes every derived metric (YoY/QoQ growth, net margin, ROE,
  current ratio, peer percentile ranking) from the normalized line items —
  nothing is hardcoded.

## Data flow

1. A ticker is submitted (via the dashboard, the API, or the CLI).
2. `SECClient` resolves the company's CIK and looks up its most recent 10-Q
   (falling back to 10-K) from `data.sec.gov`.
3. Playwright launches Chromium and opens the filing document directly on
   `sec.gov`.
4. The scraper locates the income statement, balance sheet, and cash flow
   statement tables in the rendered page and extracts every labeled row.
5. The normalizer converts raw text (`"$(2,345)"`, `"$94,036 million"`, etc.)
   into signed numeric USD values.
6. Line items are upserted into the database under the correct company and
   reporting period, derived from the filing's own reported period date.
7. The analytics engine computes ratios and peer percentiles on demand.
8. Charts (Matplotlib) and a 4-slide investor PPTX (python-pptx) are
   generated asynchronously by a Celery worker.

## CAPTCHA / anti-bot handling

The pipeline never attempts to bypass a CAPTCHA or access challenge. It
detects one, saves a screenshot and the page HTML for debugging, and either
pauses for a human to resolve it manually (demo mode) or fails the scrape
outright (headless/automated mode).

## SEC rate-limit etiquette

Every request carries a descriptive `User-Agent`, is throttled with a
configurable delay, and successful responses are cached on disk so repeated
lookups for the same ticker don't re-hit SEC servers unnecessarily.

## API hardening

- **Auth** — read (`GET`) endpoints stay open so the app is easy to demo;
  mutating endpoints (`POST /companies`, `POST /ingest`, `POST /reports`,
  `PATCH /reports/{id}/status`) require an `X-API-Key` header when
  `API_KEY` is configured. Leaving it empty (the default) disables auth for
  local development.
- **Rate limiting** — `POST /ingest` and `POST /reports` are rate-limited
  per client IP (`RATE_LIMIT_INGEST`, `RATE_LIMIT_REPORTS`), since each
  triggers a real browser scrape or PPTX render.
- **Pagination** — `GET /companies` takes `skip`/`limit` query params and
  returns `{items, total, skip, limit}`.
- **Structured errors** — every error response (404, 422 validation, 429
  rate limit, 500) comes back in one consistent shape:
  `{"error": {"status_code", "message", "path", "details"?}}`.

## Installation

```bash
python -m venv .venv
. .venv/bin/activate          # Linux/macOS
.venv\Scripts\activate        # Windows

pip install -r requirements.txt
python -m playwright install chromium
```

## Environment variables

```bash
cp .env.example .env
```

Set `SEC_USER_AGENT` to `AppName/Version your-email@example.com` — SEC EDGAR
requires a descriptive, contactable user agent on every request.

Key variables:

| Variable | Purpose |
|---|---|
| `SEC_USER_AGENT` | Required by SEC EDGAR on every request |
| `SEC_REQUEST_DELAY` | Seconds between SEC requests (politeness throttle) |
| `SCRAPER_HEADLESS` | `false` shows the live Chromium browser (demo mode) |
| `SCRAPER_SLOW_MO` | Slows down browser actions for visible demos |
| `DATABASE_URL` | SQLite by default; Postgres in Docker Compose. The API derives its async URL from this automatically |
| `CELERY_TASK_ALWAYS_EAGER` | `true` runs Celery tasks synchronously (no Redis needed) for local dev |
| `API_KEY` | Empty disables auth (default); set to require `X-API-Key` on mutating endpoints |
| `RATE_LIMIT_INGEST` / `RATE_LIMIT_REPORTS` | Per-IP rate limits (e.g. `10/minute`) on the scrape/report endpoints |

## Running the pipeline

Scrape a single company end to end from the CLI:

```bash
python scripts/run_pipeline.py AAPL --demo       # visible Chromium window
python scripts/run_pipeline.py AAPL --headless   # no UI, for automation/CI
```

Start the full application (API + dashboard together):

```bash
python scripts/start_app.py            # visible browser scraping
python scripts/start_app.py --headless # headless scraping
```

Or run each service yourself:

```bash
uvicorn src.api.main:app --reload
streamlit run src/dashboard/app.py
```

Once running, ingest a company from the dashboard sidebar or via the API:

```bash
curl -X POST http://localhost:8000/ingest -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'
```

This is the only way data enters the database — there is no seed script.

## Docker

```bash
docker compose up --build
```

Brings up PostgreSQL, Redis, the FastAPI API, a Celery worker, and the
Streamlit dashboard. Database tables are created via Alembic migrations on
startup; the database starts empty and is populated only by real ingestion
requests.

## Testing

```bash
python -m pytest tests/ -q
```

Unit and integration tests cover the normalizer, parser, analytics engine,
API routes, and PPTX/report generation. Network-dependent scraping is
exercised against a local HTML fixture (`tests/fixtures/sec_filing_mock.html`)
and by patching the ingestion entry point in isolation tests — this fixture
data is used only inside the test suite and never reaches the running
application or its database.

## Project structure

```
src/
  core/        # settings, database engine, Celery app, logging
  ingestion/   # SEC client, filing discovery, Playwright browser, scraper,
               # HTML parser, value normalizer, Celery ingestion task
  models/      # SQLAlchemy ORM models (Company, FinancialPeriod,
               # FinancialLineItem, ComputedRatio, ReportJob)
  schemas/     # Pydantic request/response models
  analytics/   # Pure, dependency-free financial ratio + percentile math
  reporting/   # Matplotlib charts, python-pptx report builder, Celery task
  api/         # FastAPI app and routers (companies, compare, reports, ingest)
  dashboard/   # Streamlit executive dashboard + API client
alembic/       # Database migrations
scripts/       # CLI entry points (run_pipeline.py, start_app.py)
tests/         # pytest suite
```

## Limitations

- SEC filing HTML structure varies by filer and can change over time; some
  filings may need statement-specific parsing adjustments.
- A CAPTCHA or access challenge requires manual resolution in demo mode, or
  causes the scrape to fail safely in headless mode.
- Live browser scraping should be run respectfully and in compliance with
  SEC's fair-access policy (descriptive User-Agent, request throttling).
