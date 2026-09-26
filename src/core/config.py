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
    LOG_JSON: bool = True
    DEBUG: bool = True

    SEC_USER_AGENT: str = "FinancialResearchAutomation/1.0 contact@example.com"
    SEC_REQUEST_DELAY: float = 1.0
    SEC_TIMEOUT: int = 30

    SCRAPER_HEADLESS: bool = False
    SCRAPER_SLOW_MO: int = 500
    SCRAPER_TIMEOUT: int = 30000
    SCRAPER_SCREENSHOTS: bool = True
    SCRAPER_SAVE_HTML: bool = True

    DATABASE_URL: str = "sqlite:///./data/fra.db"

    CACHE_TTL_SECONDS: int = 60

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False

    API_BASE_URL: str = "http://localhost:8000"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

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
