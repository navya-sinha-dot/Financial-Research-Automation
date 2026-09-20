from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"
DEBUG_DIR = DATA_DIR / "debug"
REPORTS_DIR = DATA_DIR / "reports"

DEFAULT_SEC_USER_AGENT = "FinancialResearchAutomation/1.0 contact@example.com"

STATEMENT_ALIASES = {
    "income_statement": [
        "consolidated statements of operations",
        "consolidated statements of income",
        "statements of operations",
        "income statement",
    ],
    "balance_sheet": [
        "consolidated balance sheets",
        "balance sheets",
        "balance sheet",
    ],
    "cash_flow": [
        "consolidated statements of cash flows",
        "statements of cash flows",
        "cash flow",
    ],
}

INCOME_LINE_ITEMS = [
    "Revenue",
    "Cost of Revenue",
    "Gross Profit",
    "Operating Expenses",
    "Operating Income",
    "Other Income/Expense",
    "Income Before Taxes",
    "Income Tax",
    "Net Income",
    "Basic EPS",
    "Diluted EPS",
]

BALANCE_SHEET_ITEMS = [
    "Cash and Cash Equivalents",
    "Short-Term Investments",
    "Accounts Receivable",
    "Inventory",
    "Total Current Assets",
    "Total Assets",
    "Current Liabilities",
    "Total Liabilities",
    "Shareholders' Equity",
    "Total Debt",
]

CASH_FLOW_ITEMS = [
    "Net Income",
    "Operating Cash Flow",
    "Capital Expenditure",
    "Investing Cash Flow",
    "Financing Cash Flow",
    "Free Cash Flow",
]
