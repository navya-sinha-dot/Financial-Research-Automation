# 2. Tech Stack (Simple Explanation)

This page lists every tool used in the project and explains **why** it was
picked, in plain words. No deep technical knowledge needed.

## The main programming language

| Tool | What it is | Why we used it |
|---|---|---|
| **Python** | A programming language | Easy to read, has great tools for data, web servers, and automation. Most data/finance tools use Python. |

## The web server (the "brain" that answers requests)

| Tool | What it is | Why we used it |
|---|---|---|
| **FastAPI** | A framework for building web APIs (a way for programs to talk to each other over the internet) | It's fast, modern, and automatically creates documentation for the API. |
| **Uvicorn** | The engine that actually runs the FastAPI server | FastAPI needs something to "run" it — Uvicorn is that engine. |

Think of FastAPI like a **receptionist**: it receives requests ("give me
company X's financials") and sends back an answer.

## The database (where data is stored)

| Tool | What it is | Why we used it |
|---|---|---|
| **PostgreSQL** | A powerful, free database (used when running in Docker) | Reliable, used by almost every serious company. |
| **SQLite** | A simple, file-based database (used for local testing) | No setup needed — perfect for quick testing on your own laptop. |
| **SQLAlchemy** | A tool that lets Python talk to the database using Python code instead of raw database language (SQL) | Makes the code easier to read and safer (less chance of mistakes). |
| **Alembic** | A tool that tracks changes to the database structure over time (like "track changes" in Word, but for database tables) | Lets us safely add/change tables without losing data. |

Think of the database like a **filing cabinet**: every company, every
quarter's numbers, and every report goes into labeled drawers (tables).

## The web scraper (reads the internet)

| Tool | What it is | Why we used it |
|---|---|---|
| **Playwright** | A tool that opens and controls a real Chrome browser automatically | SEC filing pages are complex webpages — Playwright can click, scroll, and read them just like a human would. |
| **BeautifulSoup** + **lxml** | Tools that read HTML (webpage code) and pull out the data we need | Much more reliable than trying to guess patterns with plain text search. |
| **tenacity** | A tool that automatically retries a task if it fails once (like a network hiccup) | The internet is not 100% reliable — this makes the scraper tougher. |
| **httpx** | A tool for making simple web requests (used for SEC's official lookup service) | Faster than opening a full browser when we just need a quick answer. |

## The background worker (does slow jobs without freezing the app)

| Tool | What it is | Why we used it |
|---|---|---|
| **Celery** | A tool that runs tasks in the background, separate from the main app | Scraping a website or building a PowerPoint file takes time — we don't want the user to wait/freeze while it happens. |
| **Redis** | A super-fast, temporary storage tool | Celery uses it to pass "job requests" between the app and the worker. We also use it to **cache** (temporarily save) answers so we don't recalculate the same thing twice. |

Think of Celery + Redis like a **restaurant kitchen**: you (the customer)
place an order (a request) and get a ticket number. The kitchen (Celery
worker) cooks in the background. You don't have to stand at the counter
waiting.

## The math / analytics

| Tool | What it is | Why we used it |
|---|---|---|
| **Pandas** | A tool for working with tables of numbers (like Excel, but in code) | Makes it easy to calculate growth rates, rankings, and averages across many companies/quarters. |
| **NumPy** | A tool for fast number calculations | Pandas uses it behind the scenes for speed. |

## The reports and charts

| Tool | What it is | Why we used it |
|---|---|---|
| **Matplotlib** | A tool that draws charts/graphs | Used to create the revenue trend and comparison charts. |
| **python-pptx** | A tool that creates PowerPoint files using code | Automatically builds the 4-slide investor report — no manual PowerPoint work. |

## The dashboard (what a user sees in the browser)

| Tool | What it is | Why we used it |
|---|---|---|
| **Streamlit** | A tool for quickly building simple web dashboards using only Python | No need to learn HTML/JavaScript — you can build a working dashboard fast. |

## Testing and code quality (making sure the code actually works)

| Tool | What it is | Why we used it |
|---|---|---|
| **pytest** | A tool that runs automated tests | Confirms the code works correctly every time, without a human manually checking. |
| **pytest-cov** | Measures how much of the code the tests actually check | Helps us find "untested" risky areas. |
| **fakeredis** | A pretend/fake version of Redis, used only during testing | Lets us test caching without needing a real Redis server running. |
| **ruff** | A tool that checks code for style mistakes and bad patterns | Keeps the code clean and consistent. |
| **black** | A tool that automatically formats code to look consistent | Saves time arguing about code style. |
| **mypy** | A tool that checks if the code's data types make sense (e.g., not mixing text and numbers by mistake) | Catches a category of bugs before the code even runs. |
| **pre-commit** | Runs the above checks automatically before code is saved to the project history | Stops mistakes from ever being committed. |

## Automatic testing pipeline (CI/CD)

| Tool | What it is | Why we used it |
|---|---|---|
| **GitHub Actions** | A robot that automatically runs tests and checks every time code is changed | Confirms nothing is broken before code gets merged, without a human having to remember to test manually. |

## Watching the app while it runs (Observability)

| Tool | What it is | Why we used it |
|---|---|---|
| **Prometheus** (via `prometheus-fastapi-instrumentator`) | A tool that collects numbers about how the app is performing (how many requests, how long they take) | Lets you see if the app is slow or having problems, like a car's dashboard gauges. |
| **python-json-logger** | Makes the app's log messages come out as structured data (JSON) instead of plain text | Easier for computers to search/filter logs later. |
| **Request ID Middleware** (custom code) | Gives every single web request a unique ID number | If something goes wrong, you can search logs for that ID and see exactly what happened for that one request. |

## Security / access control

| Tool | What it is | Why we used it |
|---|---|---|
| **API Key auth** (custom code) | A password-like secret key required to make changes through the API | Stops random people from creating fake data or triggering expensive scrapes. |
| **slowapi** | A tool that limits how many requests one user can make per minute | Stops one user from overloading the system (called **rate limiting**). |

## Running everywhere the same way

| Tool | What it is | Why we used it |
|---|---|---|
| **Docker** | A tool that packages the app with everything it needs to run, into one box ("container") | The app runs exactly the same on your laptop, a teammate's laptop, or a real server — no "it works on my machine" problems. |
| **Docker Compose** | A tool that starts multiple Docker containers together (database, server, worker, dashboard) | One command starts the whole system. |

## Quick summary (one-line tech stack for a resume)

> Python, FastAPI, SQLAlchemy (async), PostgreSQL, Celery, Redis, Playwright,
> Pandas, Streamlit, Docker, Prometheus, GitHub Actions.
