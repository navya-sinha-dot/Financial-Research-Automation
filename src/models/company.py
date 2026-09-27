from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from src.core.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticker = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100), nullable=True, default="Information Technology")
    exchange = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    periods = relationship("FinancialPeriod", back_populates="company", cascade="all, delete-orphan")
    report_jobs = relationship("ReportJob", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, ticker='{self.ticker}', name='{self.name}')>"
