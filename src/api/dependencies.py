from typing import Generator
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.core.config import settings, Settings


def get_current_settings() -> Settings:
    return settings
