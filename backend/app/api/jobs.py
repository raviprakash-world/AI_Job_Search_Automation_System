from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User
from app.schemas.jobs import JobActionRequest, JobDetailOut, JobMatchOut, JobOut, JobSnapshotOut, SavedJobOut
from app.services import job_listing_service, saved_job_service
from app.services.job_listing_service import JobListingRow

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_job_out(row: JobListingRow) -> JobOut:
    return JobOut(
        id=row.job.id,
        company_name=row.company.name if row.company else None,
        title=row.job.title,
        location=row.job.location,
        remote_status=row.job.remote_status,
        employment_type=row.job.employment_type,
        salary_min=row.job.salary_min,
        salary_max=row.job.salary_max,
        salary_currency=row.job.salary_currency,
        posting_url=row.job.posting_url,
        analysis_status=row.job.analysis_status,
        status=row.job.status,
        first_seen_at=row.job.first_seen_at,
        last_seen_at=row.job.last_seen_at,
        match=JobMatchOut.model_validate(row.match) if row.match else None,
        saved_status=row.saved.status if row.saved else None,
    )


@router.get("", response_model=list[JobOut])
async def list_jobs(
    status: str | None = None,
    min_score: float | None = None,
    company: str | None = None,
    saved_status: str | None = None,
    include_blacklisted: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await job_listing_service.list_jobs(
        db,
        current_user.id,
        status=status,
        min_score=min_score,
        company_name=company,
        saved_status=saved_status,
        include_blacklisted=include_blacklisted,
    )
    return [_to_job_out(row) for row in rows]


@router.get("/{job_id}", response_model=JobDetailOut)
async def get_job(job_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await job_listing_service.get_job_detail(db, current_user.id, job_id)
    base = _to_job_out(row)
    return JobDetailOut(
        **base.model_dump(),
        description_text=row.job.description_text,
        structured_requirements=row.job.structured_requirements,
        snapshots=[JobSnapshotOut.model_validate(s) for s in row.job.snapshots],
    )


@router.post("/{job_id}/action", response_model=SavedJobOut)
async def act_on_job(
    job_id: str,
    payload: JobActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await saved_job_service.apply_action(db, current_user.id, job_id, payload)
