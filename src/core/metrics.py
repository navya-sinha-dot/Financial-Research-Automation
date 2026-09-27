"""Prometheus metrics shared across the API process and Celery tasks.

Note on Celery: these Counters/Histograms live on the default in-process
prometheus_client registry, which is per-process. When Celery runs as a
separate worker process (the production/docker-compose setup), metrics
recorded inside a task are NOT visible on the API's own /metrics endpoint
-- that would need prometheus_client's multiprocess mode (a shared
directory + multiprocess collector), which is deliberately out of scope
here. Under CELERY_TASK_ALWAYS_EAGER=true (local/demo mode) everything runs
in one process, so the numbers below are visible on /metrics as expected.
"""

from prometheus_client import Counter, Histogram

INGESTION_TOTAL = Counter(
    "fra_ingestion_total",
    "Total SEC ingestion attempts",
    ["status"],
)
INGESTION_DURATION_SECONDS = Histogram(
    "fra_ingestion_duration_seconds",
    "Time spent scraping and ingesting a company's filings",
)

REPORT_GENERATION_TOTAL = Counter(
    "fra_report_generation_total",
    "Total PPTX report generation attempts",
    ["status"],
)
REPORT_GENERATION_DURATION_SECONDS = Histogram(
    "fra_report_generation_duration_seconds",
    "Time spent generating a PPTX investor report",
)

CACHE_HITS_TOTAL = Counter("fra_cache_hits_total", "Cache hits", ["cache_type"])
CACHE_MISSES_TOTAL = Counter("fra_cache_misses_total", "Cache misses", ["cache_type"])
