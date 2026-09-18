from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.models.company import Company
from src.models.financial import FinancialPeriod, FinancialLineItem, ComputedRatio
from src.schemas.company import CompanyResponse, CompanyCreate
from src.schemas.financial import CompanyFinancialsResponse, FinancialPeriodResponse, LineItemResponse, ComputedRatioResponse
from src.analytics.metrics import compute_period_ratios

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("", response_model=List[CompanyResponse])
def list_companies(db: Session = Depends(get_db)):
    """Retrieve all tracked companies."""
    return db.query(Company).order_by(Company.ticker).all()


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    """Register a new company."""
    existing = db.query(Company).filter_by(ticker=payload.ticker.upper()).first()
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
    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}/financials", response_model=CompanyFinancialsResponse)
def get_company_financials(company_id: int, db: Session = Depends(get_db)):
    """Retrieve all quarterly financial periods and key-value line items for a company."""
    company = db.query(Company).filter_by(id=company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found.",
        )

    periods = (
        db.query(FinancialPeriod)
        .filter_by(company_id=company.id)
        .order_by(FinancialPeriod.fiscal_year.asc(), FinancialPeriod.period_type.asc())
        .all()
    )

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
        ratios = [
            ComputedRatioResponse(id=r.id, ratio_name=r.ratio_name, value=r.value)
            for r in p.computed_ratios
        ]
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
def get_company_ratios(company_id: int, db: Session = Depends(get_db)):
    """Retrieve or compute financial ratios (YoY/QoQ growth, margins, ROE, current ratio)."""
    company = db.query(Company).filter_by(id=company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found.",
        )

    periods = (
        db.query(FinancialPeriod)
        .filter_by(company_id=company.id)
        .order_by(FinancialPeriod.fiscal_year.asc(), FinancialPeriod.report_date.asc())
        .all()
    )

    # Format periods data for pure analytics computation
    periods_data = []
    for p in periods:
        items_dict = {item.item_name: item.value for item in p.line_items}
        periods_data.append({
            "period_id": p.id,
            "period_type": p.period_type,
            "fiscal_year": p.fiscal_year,
            "report_date": p.report_date,
            "items": items_dict,
        })

    enriched = compute_period_ratios(periods_data)

    # Persist or update computed ratios in the database
    for record in enriched:
        period_id = record.get("period_id")
        computed = record.get("computed_ratios", {})
        for r_name, r_val in computed.items():
            if r_val is not None:
                ratio_row = (
                    db.query(ComputedRatio)
                    .filter_by(period_id=period_id, ratio_name=r_name)
                    .first()
                )
                if not ratio_row:
                    ratio_row = ComputedRatio(
                        period_id=period_id,
                        ratio_name=r_name,
                        value=r_val,
                    )
                    db.add(ratio_row)
                else:
                    ratio_row.value = r_val

    db.commit()

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
