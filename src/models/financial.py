from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.company import Company


class FinancialPeriod(Base):
    __tablename__ = "financial_periods"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., 'Q1', 'Q2', 'Q3', 'Q4', 'FY'
    fiscal_year: Mapped[int] = mapped_column(nullable=False)  # e.g., 2023, 2024
    report_date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (UniqueConstraint("company_id", "period_type", "fiscal_year", name="uq_company_period_year"),)

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="periods")
    line_items: Mapped[list["FinancialLineItem"]] = relationship(
        back_populates="period", cascade="all, delete-orphan"
    )
    computed_ratios: Mapped[list["ComputedRatio"]] = relationship(
        back_populates="period", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<FinancialPeriod(id={self.id}, company_id={self.company_id}, {self.period_type} {self.fiscal_year})>"


class FinancialLineItem(Base):
    """Flexible key-value metric rows allowing dynamic metrics without schema changes."""

    __tablename__ = "financial_line_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("financial_periods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g., 'revenue', 'net_income'
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), default="USD")
    source: Mapped[str | None] = mapped_column(String(100), default="scraper")

    __table_args__ = (UniqueConstraint("period_id", "item_name", name="uq_period_item_name"),)

    # Relationships
    period: Mapped["FinancialPeriod"] = relationship(back_populates="line_items")

    def __repr__(self) -> str:
        return f"<FinancialLineItem(id={self.id}, item_name='{self.item_name}', value={self.value})>"


class ComputedRatio(Base):
    __tablename__ = "computed_ratios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("financial_periods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ratio_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g., 'yoy_growth', 'roe'
    value: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("period_id", "ratio_name", name="uq_period_ratio_name"),)

    # Relationships
    period: Mapped["FinancialPeriod"] = relationship(back_populates="computed_ratios")

    def __repr__(self) -> str:
        return f"<ComputedRatio(id={self.id}, ratio_name='{self.ratio_name}', value={self.value})>"
