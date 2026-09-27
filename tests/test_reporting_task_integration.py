"""Integration test for the Celery report-generation task end to end: DB ->
API (in-process, since CELERY_TASK_ALWAYS_EAGER=true) -> charts -> PPTX file.
"""

from pathlib import Path

from src.models.company import Company
from src.models.report import ReportJob, ReportStatus
from src.reporting.tasks import generate_report_task


def test_generate_report_task_full_pipeline(seeded_db, tmp_path, monkeypatch):
    monkeypatch.setattr("src.reporting.tasks.settings.REPORTS_DIR", tmp_path)
    monkeypatch.setattr("src.reporting.tasks.settings.DATA_DIR", tmp_path)

    company = seeded_db.query(Company).filter_by(ticker="INFY").first()
    job = ReportJob(company_id=company.id, status=ReportStatus.PENDING)
    seeded_db.add(job)
    seeded_db.commit()

    result = generate_report_task(job_id=job.id, company_id=company.id)

    assert result["status"] == "COMPLETED"
    output_path = Path(result["output_path"])
    assert output_path.exists()
    assert output_path.suffix == ".pptx"

    seeded_db.refresh(job)
    assert job.status == ReportStatus.COMPLETED
    assert job.output_path == str(output_path)


def test_generate_report_task_fails_gracefully_with_no_periods(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("src.reporting.tasks.settings.REPORTS_DIR", tmp_path)
    monkeypatch.setattr("src.reporting.tasks.settings.DATA_DIR", tmp_path)

    company = Company(ticker="EMPTYCO", name="Empty Co")
    db_session.add(company)
    db_session.flush()

    job = ReportJob(company_id=company.id, status=ReportStatus.PENDING)
    db_session.add(job)
    db_session.commit()

    result = generate_report_task(job_id=job.id, company_id=company.id)

    assert result["status"] == "FAILED"
    assert "error" in result

    db_session.refresh(job)
    assert job.status == ReportStatus.FAILED
    assert job.error_message is not None
