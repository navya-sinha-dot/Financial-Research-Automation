# 3. Architecture (How Everything Fits Together)

"Architecture" just means: **how the different parts of the system are
organized, and how they talk to each other.**

## The 4 running programs (services)

When this project runs, there are 4 separate programs running at the same
time:

1. **The Database** (PostgreSQL) — stores all the data permanently.
2. **Redis** — a fast temporary storage box, used for background job queues
   and caching.
3. **The API server** (FastAPI + Uvicorn) — the only program allowed to read
   or write to the database directly. Everyone else must ask it.
4. **The Worker** (Celery) — does the slow jobs (scraping, building
   PowerPoint files) in the background.
5. **The Dashboard** (Streamlit) — the webpage a person actually looks at.

(That's 5 things, but people usually group Database + Redis as "storage.")

## The most important rule: "Only the API touches the database"

The Dashboard and the Worker are **not allowed** to directly open the
database. They must always ask the API server over the network (using
normal web requests), the same way any outside app would.

**Why this rule matters:** it means all the business logic (the rules
about how data is checked, saved, and calculated) lives in ONE place — the
API. If we ever swap the Dashboard for a totally different app (like a
mobile app), nothing about the API needs to change.

## Picture of the flow (simple diagram)

```
[ You type a ticker, e.g. "AAPL" ]
              |
              v
      [ Streamlit Dashboard ]  <-- what you see in your browser
              |
      (sends a web request)
              v
        [ FastAPI Server ]  <-- the "brain", the only one allowed to touch the database
              |
     -------------------------
     |                       |
     v                       v
[ PostgreSQL Database ]   [ Celery Worker ] <-- does slow work in background
                               |
                               v
                    [ Playwright opens Chrome ]
                               |
                               v
                    [ Reads real filing from SEC.gov ]
                               |
                               v
                    [ Saves numbers back through the API ]
```

## Step-by-step: "What happens when I ask to research a company?"

1. You type `AAPL` into the Dashboard and click "Fetch & Ingest".
2. The Dashboard sends a request to the API: `POST /ingest`.
3. The API hands this job to a Celery Worker (so the Dashboard doesn't
   freeze while waiting).
4. The Worker asks SEC's official lookup service: "What is AAPL's company ID
   (called a CIK) and where is their latest quarterly filing?"
5. The Worker opens a real Chromium browser (using Playwright) and visits
   the actual filing webpage on sec.gov.
6. It reads the Income Statement, Balance Sheet, and Cash Flow tables
   directly from the page's HTML.
7. It cleans up the numbers (turns `"$(2,345)"` into `-2345`, for example).
8. It repeats this for the last few quarters (called "backfill"), reusing
   the same browser tab to be faster and look more natural.
9. The Worker saves everything into the database (Company, Period, and
   Line Item rows).
10. The Dashboard shows a success message.

## Step-by-step: "What happens when I ask for a PowerPoint report?"

1. You click "Generate PPTX Report" in the Dashboard.
2. The Dashboard calls `POST /reports` on the API.
3. The API creates a "Report Job" row in the database with status
   `PENDING`, and hands the actual work to a Celery Worker.
4. The Worker asks the API (over the network, not directly) for:
   - The company's financial numbers.
   - The calculated ratios.
   - A list of peer companies to compare against.
5. The Worker draws 3 charts (using Matplotlib).
6. The Worker builds a 4-slide PowerPoint file (using python-pptx).
7. The Worker tells the API the job is `COMPLETED` and where the file is.
8. The Dashboard shows a "Download" button.

## Why two kinds of database connections (sync and async)?

This is a slightly technical detail, explained simply:

- **Sync** means "do one thing, wait for it to finish, then do the next
  thing." This is simple and used by the Celery Worker (workers process
  one job at a time anyway, so there's no benefit to complexity).
- **Async** means "can handle many things at once without waiting." This is
  used by the FastAPI web server, because a real web server needs to answer
  many different users' requests at the same time. If it could only do one
  at a time, one slow request would freeze the entire server for everyone
  else.

So: **API server = async** (handles many users at once). **Worker = sync**
(only ever doing one background job at a time, so simple is better).

## Why does the scraper act "human-like"?

The scraper is built to avoid looking like a robot, without breaking any
rules:

- It sends a real "who am I" label (User-Agent) on every request, as SEC
  itself asks scrapers to do.
- It waits a random amount of time between actions, like a real person
  reading a page (called **rate limiting** / **politeness delay**).
- It uses a real browser with realistic settings (screen size, browser
  version) instead of a bare script.
- If it sees a "prove you are human" test (CAPTCHA), it does **not** try to
  trick or bypass it. It stops safely and reports the problem.

## Why cache anything?

**Caching** means: "save an answer temporarily so if someone asks the same
question again soon, we can answer instantly instead of recalculating."

Example: comparing 5 companies' ratios involves a lot of math. If two
people ask for the same comparison within 60 seconds, the second person
gets an instant answer from the cache (Redis) instead of the system doing
all the math again.

If Redis is turned off or not working, the app doesn't crash — it just
skips the cache and calculates normally (a little slower, but still
correct). This is called "graceful degradation."

## Why rate limits and API keys?

- **Rate limiting**: stops one person (or a mistake in code) from asking
  for 1,000 expensive scrapes in one minute and overloading the system.
- **API key**: a simple password that must be sent when doing something
  that changes data (like starting a scrape). Anyone can still *look* at
  data without a key (read-only access is open), but *creating or changing*
  data requires the key. This is a common, simple way to add safety to an
  API without building a full login system.

## Why automated tests and CI/CD?

Every time code is changed, a robot (GitHub Actions) automatically:

1. Checks the code style is clean (**ruff**, **black**).
2. Checks the data types make sense (**mypy**).
3. Runs all 70+ tests to make sure nothing broke (**pytest**).
4. Tries building the whole app in a Docker container, to make sure it
   would actually deploy correctly.

This catches mistakes **before** they reach real users, instead of finding
out something is broken after it's already live.
