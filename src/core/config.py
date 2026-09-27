from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = True

    SEC_USER_AGENT: str = "FinancialResearchAutomation/1.0 contact@example.com"
    SEC_REQUEST_DELAY: float = 1.0
    SEC_REQUEST_JITTER: float = 0.6
    SEC_TIMEOUT: int = 30
    SEC_MAX_RETRIES: int = 4
    SEC_CACHE_TTL_SECONDS: int = 86400

    SCRAPER_HEADLESS: bool = False
    SCRAPER_SLOW_MO: int = 500
    SCRAPER_TIMEOUT: int = 30000
    SCRAPER_SCREENSHOTS: bool = True
    SCRAPER_SAVE_HTML: bool = True
    SCRAPER_MAX_RETRIES: int = 3
    SCRAPER_MIN_DELAY_MS: int = 250
    SCRAPER_MAX_DELAY_MS: int = 900
    SCRAPER_BACKFILL_QUARTERS: int = 4

    DATABASE_URL: str = "sqlite:///./data/fra.db"

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False

    API_BASE_URL: str = "http://localhost:8000"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    # Empty string disables auth entirely -- convenient for local/demo use.
    # Set a real value to require `X-API-Key` on mutating endpoints.
    API_KEY: str = ""
    RATE_LIMIT_INGEST: str = "10/minute"
    RATE_LIMIT_REPORTS: str = "15/minute"

    STREAMLIT_SERVER_PORT: int = 8501
    STREAMLIT_SERVER_ADDRESS: str = "0.0.0.0"

    DATA_DIR: Path = Path("data")
    RAW_DIR: Path = Path("data/raw")
    PROCESSED_DIR: Path = Path("data/processed")
    CACHE_DIR: Path = Path("data/cache")
    DEBUG_DIR: Path = Path("data/debug")
    REPORTS_DIR: Path = Path("data/reports")

    def ensure_directories(self) -> None:
        """Ensure all required data directories exist."""
        for path in [self.DATA_DIR, self.RAW_DIR, self.PROCESSED_DIR, self.CACHE_DIR, self.DEBUG_DIR, self.REPORTS_DIR]:
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
