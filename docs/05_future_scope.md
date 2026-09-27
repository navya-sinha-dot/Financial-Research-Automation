# 5. Future Scope (What Could Be Added Next)

This project already works end-to-end, but no project is ever "100%
finished." Here are realistic ideas for what could be added next, grouped
by type. Great to mention in an interview when asked "what would you
improve?"

## More data coverage

- **Annual reports (10-K), not just quarterly (10-Q)** — currently the
  system prefers 10-Q but can fall back to 10-K. Full support for
  side-by-side quarterly + annual analysis would be a nice addition.
- **More filing types** — like 8-K (special events, e.g. mergers) for
  early alerts.
- **International companies** — SEC EDGAR only covers US-listed companies.
  Supporting other countries' regulators would need new scraping logic per
  country.
- **More financial ratios** — e.g. Debt-to-Equity, Quick Ratio, Earnings
  Per Share (EPS) growth, Free Cash Flow yield.
- **Sector benchmarks** — comparing a company not just to a few peers you
  pick, but to its entire industry average.

## Smarter automation

- **Scheduled/automatic re-scraping** — automatically re-check for new
  filings every day/week for companies you're tracking, instead of asking
  manually every time.
- **Alerts** — send an email or Slack message when a tracked company files
  a new report, or when a ratio crosses a certain threshold (e.g. "ROE
  dropped below 10%").
- **AI-written commentary** — use a language model to write a short,
  plain-English summary paragraph inside the PowerPoint report (e.g. "This
  quarter's revenue grew faster than the prior 3 quarters, driven by...").
- **Anomaly detection** — automatically flag if a scraped number looks
  wrong (like a Revenue number that's 1000x too big due to a units mix-up),
  instead of trusting every number blindly.

## Making the system stronger for many users

- **User accounts / login** — right now everyone shares the same system.
  Adding accounts would let each analyst track their own watchlist.
- **Multiple report templates** — different PowerPoint styles for
  different audiences (quick summary vs. detailed deep-dive).
- **Scale the workers** — run many Celery workers at once (instead of one),
  so many companies can be scraped in parallel, using tools like
  **Kubernetes** to manage that automatically.
- **Full metrics across all workers** — right now, the background workers'
  performance numbers (like scrape success/failure) only show up on the
  same monitoring dashboard if everything runs in a single process. Making
  this work cleanly across many separate worker machines would need
  Prometheus's "multiprocess mode" — a known, deliberately-skipped piece
  for now.

## Better frontend / user experience

- **Replace Streamlit with a full frontend** (like React) for a more
  polished, production-quality look and feel, and more custom design
  control than Streamlit allows.
- **Interactive charts** (hover to see exact numbers) instead of static
  images in the PowerPoint.
- **Export to other formats** — Excel workbook, PDF, or a Word document, not
  just PowerPoint.

## Stronger data quality and trust

- **Track filing history changes** — if a company restates old numbers
  (this happens sometimes), keep a version history instead of overwriting.
- **Source citations** — automatically link each number in the report back
  to the exact filing and page it came from, for auditability.
- **Data validation rules** — e.g. warn if Total Assets don't roughly
  balance with Total Liabilities + Equity, which would suggest a scraping
  or parsing bug.

## Security and access

- **Real user authentication** (like login with email/password, or
  "Sign in with Google") instead of a single shared API key.
- **Role-based permissions** — e.g. "viewers" can only read reports,
  "admins" can trigger new scrapes.

---

**How to talk about this in an interview:** pick 2–3 of these that are
most relevant to the role, and explain them briefly. It shows you
understand the project isn't "done" — you know what a real production
version would need next.
