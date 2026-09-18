"""Initial database schema migration

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-18 10:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("exchange", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_companies_id"), "companies", ["id"], unique=False)
    op.create_index(op.f("ix_companies_ticker"), "companies", ["ticker"], unique=True)

    # 2. financial_periods table
    op.create_table(
        "financial_periods",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_type", sa.String(length=20), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.UniqueConstraint("company_id", "period_type", "fiscal_year", name="uq_company_period_year"),
    )
    op.create_index(op.f("ix_financial_periods_id"), "financial_periods", ["id"], unique=False)
    op.create_index(op.f("ix_financial_periods_company_id"), "financial_periods", ["company_id"], unique=False)

    # 3. financial_line_items table (flexible key-value rows)
    op.create_table(
        "financial_line_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("financial_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_name", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.UniqueConstraint("period_id", "item_name", name="uq_period_item_name"),
    )
    op.create_index(op.f("ix_financial_line_items_id"), "financial_line_items", ["id"], unique=False)
    op.create_index(op.f("ix_financial_line_items_period_id"), "financial_line_items", ["period_id"], unique=False)
    op.create_index(op.f("ix_financial_line_items_item_name"), "financial_line_items", ["item_name"], unique=False)

    # 4. computed_ratios table
    op.create_table(
        "computed_ratios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("financial_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ratio_name", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.UniqueConstraint("period_id", "ratio_name", name="uq_period_ratio_name"),
    )
    op.create_index(op.f("ix_computed_ratios_id"), "computed_ratios", ["id"], unique=False)
    op.create_index(op.f("ix_computed_ratios_period_id"), "computed_ratios", ["period_id"], unique=False)
    op.create_index(op.f("ix_computed_ratios_ratio_name"), "computed_ratios", ["ratio_name"], unique=False)

    # 5. report_jobs table
    op.create_table(
        "report_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="reportstatus"), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("output_path", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
    )
    op.create_index(op.f("ix_report_jobs_id"), "report_jobs", ["id"], unique=False)
    op.create_index(op.f("ix_report_jobs_company_id"), "report_jobs", ["company_id"], unique=False)
    op.create_index(op.f("ix_report_jobs_status"), "report_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("report_jobs")
    op.drop_table("computed_ratios")
    op.drop_table("financial_line_items")
    op.drop_table("financial_periods")
    op.drop_table("companies")
