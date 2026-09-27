# 6. Interview Questions & Simple Answers

This page has two parts:

- **Part A: Technical questions** (about the code/system)
- **Part B: Business & Analyst questions** (about finance concepts used)

All answers are written in **very simple language**. Read them, understand
them, then explain them **in your own words** in the actual interview —
don't just memorize word-for-word.

---

# Part A: Technical Questions

### Q1. What does this project do, in one sentence?

It's a tool that automatically reads a company's real financial filings
from the SEC website, calculates key ratios, and builds a PowerPoint report
— without any manual data entry.

### Q2. Walk me through what happens when a user researches a company.

1. User types a ticker (like `AAPL`) into the dashboard.
2. The dashboard asks the API to start a scrape.
3. The API hands the job to a background worker (so the app doesn't freeze).
4. The worker opens a real browser, visits the actual filing page on
   sec.gov, and reads the numbers.
5. The numbers are cleaned up and saved to the database.
6. Ratios are calculated (growth, margins, ROE, etc.).
7. The user can then ask for a PowerPoint report, which pulls this data,
   draws charts, and builds the slides.

### Q3. Why did you use a real browser (Playwright) instead of just an API call?

The company's filing page is a normal webpage, not a clean data API.
A real browser can load the page exactly like a human would, which is more
reliable for reading data that's inside complex HTML tables. It also lets
the tool detect things like "prove you're human" tests properly.

### Q4. How do you make sure you don't get blocked while scraping?

A few simple things: identify yourself honestly (a proper "User-Agent"
label, as SEC's own rules ask), wait a little between requests instead of
hammering the site, and use realistic browser settings. This is called
being a "polite" scraper. If a block or CAPTCHA does appear, the tool stops
safely instead of trying to trick or bypass it.

### Q5. Why FastAPI instead of Flask or Django?

FastAPI is built for speed and modern Python. It automatically checks that
incoming requests have the right data shape, and it automatically generates
API documentation. It also natively supports **async** code, which matters
for a web server that needs to handle many users at once.

### Q6. What is "async" and why does it matter here?

Async means a program can start one task, and while waiting for it to
finish (like waiting for the database), it can go work on a different
request instead of just sitting idle. This lets one web server handle many
users at the same time efficiently. The API server uses async; the
background worker does not need to, because a worker only ever processes
one job at a time anyway.

### Q7. Why do you have both a "sync" and "async" database connection?

The background worker (Celery) processes one job at a time by design, so
there's no benefit to async there — keeping it simple (sync) is better.
The web API, on the other hand, needs to serve many users at once, so it
uses async so it isn't blocked waiting on the database.

### Q8. What is Celery and why not just do everything directly in the API?

Celery lets slow tasks (like scraping a webpage, which can take many
seconds) run in the background instead of making the user's request wait
and possibly time out. The API just says "start this job" and immediately
replies to the user; the actual work happens separately.

### Q9. What is Redis used for here?

Two things: (1) it's the message system Celery uses to pass job requests to
workers, and (2) it's used as a **cache** — a temporary storage for
answers we've already calculated, so repeat requests are instant instead of
redoing the same math.

### Q10. What is caching, and what happens if the cache (Redis) is down?

Caching means saving a recent answer so you don't have to redo the work if
someone asks the same question again soon. If Redis is down, the app
doesn't crash — it just skips the cache and calculates the answer normally
(a bit slower, but still correct). This is called "graceful degradation."

### Q11. What is rate limiting, and why did you add it?

Rate limiting means capping how many times someone can call an expensive
feature (like starting a scrape) per minute. It protects the system from
being accidentally or deliberately overloaded by one user.

### Q12. How is the API secured?

Anyone can read data (that's open on purpose, so it's easy to browse and
demo). But anything that changes data — creating a company, starting a
scrape, generating a report — requires a secret key sent in a request
header (`X-API-Key`). Without the right key, the request is rejected.

### Q13. What testing did you do? How confident are you the code works?

There are more than 70 automated tests, checking about 85% of all the code
lines. Tests cover: the math (ratios), the scraper's saving logic, the
API's responses (including error cases like "company not found"), and the
caching behavior — including what happens when things fail (bad input,
missing data, Redis being down).

### Q14. What is CI/CD, and what does yours actually check?

CI/CD means: every time code changes, a robot automatically checks it.
Ours (GitHub Actions) checks 4 things automatically: code style is clean,
data types make sense, all tests pass, and the whole app can still be
built into a Docker container. If any check fails, you know immediately —
you don't have to wait for someone to notice a bug later.

### Q15. What is database migration (Alembic), and why not just edit the database directly?

A migration is a saved, trackable "recipe" for changing the database
structure (like adding a new column). Instead of manually changing a live
database (risky, and no history of what changed), you write a migration
file, which anyone can run to apply the exact same change safely and
repeatably — like version control, but for the database's shape.

### Q16. What would you do differently, or what's a weakness of this project?

Good honest answer: the system currently keeps the latest few quarters of
history, and metrics from background workers only fully show up on the
monitoring dashboard when everything runs in one process. Scaling to many
separate worker machines would need Prometheus's "multiprocess mode,"
which wasn't built yet — it's a known, deliberate trade-off, not an
oversight.

### Q17. How would this scale if 10,000 people used it at once?

The API is already async, so it can handle many requests without
blocking. For a much bigger scale, you'd run multiple copies of the API
server behind a load balancer, run many Celery workers in parallel instead
of one, and probably move from SQLite/one Postgres box to a bigger managed
database. This is standard "add more machines" (horizontal scaling), not a
rewrite.

### Q18. Explain the difference between the Dashboard, the API, and the Worker in one line each.

- **Dashboard**: what the user sees and clicks on.
- **API**: the only program allowed to touch the database; answers
  requests.
- **Worker**: does slow background jobs (scraping, report building) so the
  API/Dashboard never freeze.

### Q19. Why keep the analytics/math code (`analytics/metrics.py`) separate, with no database code in it?

Because it makes it very easy to test: you just feed it plain numbers and
check the answer, with nothing else (no database, no network) that could
make the test slow or flaky. It's also reusable — if we ever calculate
ratios somewhere else in the app, the same trusted function can be reused.

### Q20. What was the hardest technical part of this project?

Good honest answer: getting the web scraper to reliably read numbers out of
real, messy financial filing pages (different companies format their
tables slightly differently), and making the API layer properly
asynchronous while keeping the background worker simple and synchronous at
the same time, without breaking either one.

---

# Part B: Business & Financial Analyst Questions

### Q1. Why would a financial analyst actually want this tool?

Pulling numbers from filings and building comparison reports by hand takes
hours per company. This tool does it in minutes and reduces manual
data-entry mistakes, so the analyst can spend more time on the actual
thinking (interpreting the numbers) instead of the copy-pasting.

### Q2. What is a 10-Q filing?

A 10-Q is a report that public companies in the US must file every quarter
(3 months) with the SEC. It contains the company's financial statements
(income statement, balance sheet, cash flow) for that period.

### Q3. What is a 10-K filing, and how is it different from a 10-Q?

A 10-K is the **annual** version — filed once a year, and much more
detailed than a 10-Q (it includes more disclosures, risk factors, and
audited financials). A 10-Q is a shorter, quarterly check-in.

### Q4. What is YoY growth and QoQ growth?

- **YoY (Year-over-Year)**: comparing this quarter to the *same* quarter
  last year (e.g. Q2 2024 vs Q2 2023). This removes seasonal effects (like
  retail always being busier in Q4).
- **QoQ (Quarter-over-Quarter)**: comparing this quarter to the *previous*
  quarter (e.g. Q2 2024 vs Q1 2024). This shows short-term momentum.

### Q5. What is Net Margin, and why does it matter?

Net Margin = Net Income ÷ Revenue. It shows what percentage of every
dollar of sales actually becomes profit after all expenses. A higher net
margin generally means the company is more efficient at turning sales into
profit.

### Q6. What is Return on Equity (ROE), and why does it matter?

ROE = Net Income ÷ Total Shareholders' Equity. It shows how much profit a
company generates for every dollar shareholders have invested. Investors
use it to judge how efficiently a company uses the money it's been given.

### Q7. What is the Current Ratio, and what does a high or low number mean?

Current Ratio = Current Assets ÷ Current Liabilities. It measures whether
a company has enough short-term resources to pay its short-term bills.
- A ratio **above 1** generally means the company can cover its short-term
  debts.
- A ratio that's **too low** (below 1) can be a warning sign of cash
  problems.
- A ratio that's **very high** isn't always great either — it might mean
  the company is holding too much idle cash instead of investing it.

### Q8. What is "peer comparison" in equity research, and why is it useful?

Peer comparison means looking at a company's numbers next to similar
companies (same industry, similar size) instead of looking at the number
alone. A 15% profit margin might sound great, but if every competitor in
that industry has a 25% margin, that context changes the story completely.

### Q9. What is a "percentile ranking," in simple terms?

If a company is in the 80th percentile for net margin among its peers, it
means it has a higher margin than 80% of the companies it's being compared
to. It's a simple way to turn a raw number into "how good is this,
relatively."

### Q10. What are the risks of relying on automated/scraped financial data?

- The scraper could misread a number if a company formats their filing
  differently than expected (structure changes between companies/filers).
- Data is only as fresh as the last scrape — if you don't re-scrape, you
  might be looking at stale numbers.
- Automated tools should support human judgment, not replace it —
  especially before making real investment decisions.

This project reduces (but doesn't eliminate) that risk by failing loudly
instead of guessing, and by only using the company's own official numbers
(no smoothing, no faking).

### Q11. If a company changes its filing format, what would break, and how would you notice?

The scraper looks for specific table headers (like "CONSOLIDATED STATEMENTS
OF OPERATIONS"). If a company renames or restructures that table
unusually, the scraper might fail to find the numbers for that company. You
would notice because the ingestion would return "no data" or an error
instead of silently returning wrong numbers — the system is designed to
fail loudly rather than guess.

### Q12. How could this tool help in preparing an investment pitch or research note?

It automates the boring, repetitive part (pulling and organizing numbers,
building comparison charts and tables), so the analyst can spend more time
on the actual investment argument — the "why" behind the numbers — instead
of manual data collection.

### Q13. Why is it important that all data comes from SEC EDGAR and not a paid provider?

SEC EDGAR is the free, official, legally-required source — every public US
company must file there. Using it means the numbers are the same "source
of truth" that regulators and every professional analyst ultimately relies
on, without needing an expensive data subscription.

### Q14. What's one limitation an analyst should know before trusting this tool's output?

It currently only pulls the most recent few quarters and only from
US-listed companies filing on SEC EDGAR. It's a research accelerator, not
a replacement for reading the actual filing when making a real decision.

### Q15. How would you explain "automation" value to a non-technical manager?

"This turns a task that took an analyst 2–3 hours per company (finding the
filing, copying numbers, calculating ratios, building slides) into
something that takes a few minutes, with fewer manual mistakes — freeing
up analyst time for actual analysis and judgment calls instead of data
entry."
