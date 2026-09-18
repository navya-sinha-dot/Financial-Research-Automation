from datetime import date
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from src.core.database import Base


class FinancialPeriod(Base):
    __tablename__ = "financial_periods"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    period_type = Column(String(20), nullable=False)  # e.g., 'Q1', 'Q2', 'Q3', 'Q4', 'FY'
    fiscal_year = Column(Integer, nullable=False)     # e.g., 2023, 2024
    report_date = Column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "period_type", "fiscal_year", name="uq_company_period_year"),
    )

    # Relationships
    company = relationship("Company", back_populates="periods")
    line_items = relationship("FinancialLineItem", back_populates="period", cascade="all, delete-orphan")
    computed_ratios = relationship("ComputedRatio", back_populates="period", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<FinancialPeriod(id={self.id}, company_id={self.company_id}, {self.period_type} {self.fiscal_year})>"


class FinancialLineItem(Base):
    """Flexible key-value metric rows allowing dynamic metrics without schema changes."""
    __tablename__ = "financial_line_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    period_id = Column(Integer, ForeignKey("financial_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name = Column(String(100), nullable=False, index=True)  # e.g., 'revenue', 'net_income', 'total_equity'
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=True, default="USD")
    source = Column(String(100), nullable=True, default="scraper")

    __table_args__ = (
        UniqueConstraint("period_id", "item_name", name="uq_period_item_name"),
    )

    # Relationships
    period = relationship("FinancialPeriod", back_populates="line_items")

    def __repr__(self) -> str:
        return f"<FinancialLineItem(id={self.id}, item_name='{self.item_name}', value={self.value})>"


class ComputedRatio(Base):
    __tablename__ = "computed_ratios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    period_id = Column(Integer, ForeignKey("financial_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    ratio_name = Column(String(100), nullable=False, index=True)  # e.g., 'yoy_growth', 'net_margin', 'roe'
    value = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("period_id", "ratio_name", name="uq_period_ratio_name"),
    )

    # Relationships
    period = relationship("FinancialPeriod", back_populates="computed_ratios")

    def __repr__(self) -> str:
        return f"<ComputedRatio(id={self.id}, ratio_name='{self.ratio_name}', value={self.value})>"
