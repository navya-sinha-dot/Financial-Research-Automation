"""Ingestion package for SEC EDGAR workflows.

The package intentionally avoids eager imports at import time because the scraper,
browser, and parser modules reference one another during initialization. Importing
them lazily keeps the package importable while allowing callers to load only the
functions they need.
"""

__all__ = []
