from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.middleware import RequestIdMiddleware
from src.api.routers import companies, compare, ingestion, reports
from src.core.config import settings
from src.core.database import Base, engine
from src.core.logging_config import configure_logging
import logging

import src.models  # Register all models

configure_logging(level=settings.LOG_LEVEL, json_logs=settings.LOG_JSON)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist on startup if SQLite or testing
    Base.metadata.create_all(bind=engine)
    settings.ensure_directories()
    logger.info("Financial Research Automation (FRA) API started.")
    yield
    logger.info("Financial Research Automation (FRA) API shut down.")


app = FastAPI(
    title="Financial Research Automation API",
    description="REST API for financial scraping, metrics calculation, peer benchmarking, and PPTX investor report generation.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request correlation ID + structured per-request access logging
app.add_middleware(RequestIdMiddleware)

# Prometheus metrics: request count/latency histograms auto-instrumented,
# plus the custom counters/histograms in src.core.metrics, all exposed here.
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Include Routers
app.include_router(companies.router)
app.include_router(compare.router)
app.include_router(reports.router)
app.include_router(ingestion.router)


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for container orchestrators and monitoring."""
    return {"status": "healthy", "environment": settings.ENVIRONMENT, "version": "1.0.0"}


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "Financial Research Automation (FRA) API",
        "docs_url": "/docs",
        "health_url": "/health",
        "metrics_url": "/metrics",
    }
