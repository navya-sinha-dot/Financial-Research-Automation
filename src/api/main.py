import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.database import engine, Base
import src.models  # Register all models
from src.api.routers import companies, compare, reports, ingestion

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
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
    }
