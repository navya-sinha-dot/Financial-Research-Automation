# 1. Project Overview (Simple Explanation)

## What is this project?

This project is called **Financial Research Automation** (FRA).

In simple words: it is a robot that reads company financial reports from the
internet, does the math on them, and creates a PowerPoint report for you —
all by itself, with no human typing numbers into Excel.

## What problem does it solve?

Today, if an analyst wants to study a company's financials, they usually:

1. Go to a website (like SEC.gov) and find the company's quarterly report.
2. Copy numbers like Revenue, Net Income, Total Assets into Excel by hand.
3. Calculate ratios like growth %, profit margin, ROE by hand.
4. Build slides/charts to present the findings.

This is slow, boring, and easy to get wrong (typing mistakes, missed numbers).

**This project does all 4 steps automatically.** You just type a company's
stock ticker (like `AAPL` for Apple), and the system:

1. Opens a real web browser and goes to the SEC's official filing website.
2. Finds the company's latest quarterly reports (called **10-Q** filings).
3. Reads the numbers directly from the report (Revenue, Net Income, etc.).
4. Saves those numbers in a database.
5. Calculates financial ratios (growth, margins, ROE, etc.).
6. Compares the company to other companies (peer comparison).
7. Builds charts and a 4-slide PowerPoint report — ready to send to anyone.

## Where does the data come from?

All numbers come from **SEC EDGAR** — this is the official, free, public
website run by the U.S. government (the SEC = Securities and Exchange
Commission) where every public company must publish its financial reports
by law. So the data is real and trustworthy, not made up.

There is **no fake or sample data** anywhere in this project. If the scraper
cannot read a real filing, it fails loudly instead of showing made-up
numbers. This is an important design choice — better to say "I don't know"
than to lie with fake numbers.

## Who would use something like this?

- **Equity research analysts** — to quickly pull numbers for many companies.
- **Investment banking analysts** — for building comparison tables (comps).
- **Individual investors** — to research a stock before buying.
- **Students/learners** — to practice reading financial statements.

## What does the final output look like?

A 4-slide PowerPoint file:

- **Slide 1:** Title slide with company name, ticker, sector, date.
- **Slide 2:** Key numbers (Revenue, Net Margin, ROE, Current Ratio) + a table
  of all quarters.
- **Slide 3:** Charts showing Revenue/Profit trend over time.
- **Slide 4:** How this company compares to similar companies (peer ranking).

## Key numbers about this project (good for a resume/interview)

- Scrapes real filings using a real browser (**Playwright**), not a fake
  API — this shows real web-scraping skill.
- Calculates **5 core financial ratios** automatically (YoY growth, QoQ
  growth, net margin, ROE, current ratio) for every quarter.
- Looks at up to **4 quarters of history** per company for trend analysis.
- Has **70+ automated tests** checking the code works correctly, with
  **85% test coverage** (test coverage = how much of the code the tests
  actually check).
- Has an automatic quality-check pipeline (**CI/CD**) that runs every time
  code changes, so bugs are caught early.
- Built to run in **Docker** containers, so it can run the same way on any
  computer or server.

## What is NOT this project (to avoid confusion)

- It is **not** a stock price predictor. It does not guess future prices.
- It is **not** connected to a paid data provider (like Bloomberg). It only
  uses free, public SEC data.
- It does **not** try to bypass security systems or hack anything. If SEC's
  website shows a "prove you're human" test, the tool stops safely instead
  of trying to trick it.
