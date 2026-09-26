from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.analytics.metrics import compute_period_ratios
from src.api.security import require_api_key
from src.core.database import get_async_db
from src.models.company import Company
from src.models.financial import ComputedRatio, FinancialPeriod
from src.schemas.company import CompanyCreate, CompanyResponse, PaginatedCompanyResponse
from src.schemas.financial import (
    ComputedRatioResponse,
    CompanyFinancialsResponse,
    FinancialPeriodResponse,
    LineItemResponse,
)

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("", response_model=PaginatedCompanyResponse)
async def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
):
    """Retrieve tracked companies, paginated."""
    total = (await db.execute(select(func.count()).select_from(Company))).scalar_one()
    result = await db.execute(select(Company).order_by(Company.ticker).offset(skip).limit(limit))
    companies = result.scalars().all()
    return PaginatedCompanyResponse(items=companies, total=total, skip=skip, limit=limit)


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def create_company(payload: CompanyCreate, db: AsyncSession = Depends(get_async_db)):
    """Register a new company."""
    existing = (await db.execute(select(Company).filter_by(ticker=payload.ticker.upper()))).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Company with ticker '{payload.ticker.upper()}' already exists.",
        )
    company = Company(
        ticker=payload.ticker.upper(),
        name=payload.name,
        sector=payload.sector,
        exchange=payload.exchange,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


@router.get("/{company_id}/financials", response_model=CompanyFinancialsResponse)
async def get_company_financials(company_id: int, db: AsyncSession = Depends(get_async_db)):
    """Retrieve all quarterly financial periods and key-value line items for a company."""
    company = (await db.execute(select(Company).filter_by(id=company_id))).scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found.",
        )

    result = await db.execute(
        select(FinancialPeriod)
        .filter_by(company_id=company.id)
        .options(
            selectinload(FinancialPeriod.line_items),
            selectinload(FinancialPeriod.computed_ratios),
        )
        .order_by(FinancialPeriod.fiscal_year.asc(), FinancialPeriod.period_type.asc())
    )
    periods = result.scalars().all()

    periods_response = []
    for p in periods:
        items = [
            LineItemResponse(
                id=item.id,
                item_name=item.item_name,
                value=item.value,
                unit=item.unit,
                source=item.source,
            )
            for item in p.line_items
        ]
        ratios = [ComputedRatioResponse(id=r.id, ratio_name=r.ratio_name, value=r.value) for r in p.computed_ratios]
        periods_response.append(
            FinancialPeriodResponse(
                id=p.id,
                company_id=p.company_id,
                period_type=p.period_type,
                fiscal_year=p.fiscal_year,
                report_date=p.report_date,
                line_items=items,
                computed_ratios=ratios,
            )
        )

    return CompanyFinancialsResponse(
        company_id=company.id,
        ticker=company.ticker,
        name=company.name,
        periods=periods_response,
    )


@router.get("/{company_id}/ratios")
async def get_company_ratios(company_id: int, db: AsyncSession = Depends(get_async_db)):
    """Retrieve or compute financial ratios (YoY/QoQ growth, margins, ROE, current ratio)."""
    company = (await db.execute(select(Company).filter_by(id=company_id))).scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found.",
        )

    result = await db.execute(
        select(FinancialPeriod)
        .filter_by(company_id=company.id)
        .options(selectinload(FinancialPeriod.line_items))
        .order_by(FinancialPeriod.fiscal_year.asc(), FinancialPeriod.report_date.asc())
    )
    periods = result.scalars().all()

    # Format periods data for pure analytics computation
    periods_data = []
    for p in periods:
        items_dict = {item.item_name: item.value for item in p.line_items}
        periods_data.append(
            {
                "period_id": p.id,
                "period_type": p.period_type,
                "fiscal_year": p.fiscal_year,
                "report_date": p.report_date,
                "items": items_dict,
            }
        )

    enriched = compute_period_ratios(periods_data)

    # Persist or update computed ratios in the database
    for record in enriched:
        period_id = record.get("period_id")
        computed = record.get("computed_ratios", {})
        for r_name, r_val in computed.items():
            if r_val is None:
                continue
            ratio_row = (
                await db.execute(select(ComputedRatio).filter_by(period_id=period_id, ratio_name=r_name))
            ).scalar_one_or_none()
            if not ratio_row:
                db.add(ComputedRatio(period_id=period_id, ratio_name=r_name, value=r_val))
            else:
                ratio_row.value = r_val

    await db.commit()

    return {
        "company_id": company.id,
        "ticker": company.ticker,
        "name": company.name,
        "ratios_by_period": [
            {
                "period_id": r.get("period_id"),
                "period_type": r.get("period_type"),
                "fiscal_year": r.get("fiscal_year"),
                "report_date": str(r.get("report_date")),
                "computed_ratios": r.get("computed_ratios"),
            }
            for r in enriched
        ],
    }
