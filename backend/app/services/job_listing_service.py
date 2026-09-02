from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.db.models import Company, Job, JobMatch, SavedJob, UserPreference
from app.services.job_normalization import normalize_text


@dataclass
class JobListingRow:
    job: Job
    company: Company | None
    match: JobMatch | None
    saved: SavedJob | None


async def _get_preference(db: AsyncSession, user_id: str) -> UserPreference | None:
    return await db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))


async def list_jobs(
    db: AsyncSession,
    user_id: str,
    *,
    status: str | None = None,
    min_score: float | None = None,
    company_name: str | None = None,
    saved_status: str | None = None,
    include_blacklisted: bool = False,
) -> list[JobListingRow]:
    stmt = select(Job).options(selectinload(Job.company))
    if status:
        stmt = stmt.where(Job.status == status)
    if company_name:
        stmt = stmt.where(Job.company.has(Company.normalized_name.contains(normalize_text(company_name))))

    jobs = list(await db.scalars(stmt))

    preference = await _get_preference(db, user_id)
    blacklisted = {normalize_text(c) for c in (preference.blacklisted_companies if preference else [])}
    blacklisted_roles = {normalize_text(r) for r in (preference.blacklisted_roles if preference else [])}

    job_ids = [j.id for j in jobs]
    matches: dict[str, JobMatch] = {}
    saved: dict[str, SavedJob] = {}
    if job_ids:
        match_rows = await db.scalars(
            select(JobMatch).where(JobMatch.job_id.in_(job_ids), JobMatch.user_id == user_id)
        )
        matches = {m.job_id: m for m in match_rows}
        saved_rows = await db.scalars(
            select(SavedJob).where(SavedJob.job_id.in_(job_ids), SavedJob.user_id == user_id)
        )
        saved = {s.job_id: s for s in saved_rows}

    rows = []
    for job in jobs:
        if not include_blacklisted and job.company and job.company.normalized_name in blacklisted:
            continue
        if normalize_text(job.title) in blacklisted_roles and not include_blacklisted:
            continue

        match = matches.get(job.id)
        if min_score is not None and (match is None or match.fit_score < min_score):
            continue

        saved_row = saved.get(job.id)
        if saved_status and (saved_row is None or saved_row.status != saved_status):
            continue

        rows.append(JobListingRow(job=job, company=job.company, match=match, saved=saved_row))

    rows.sort(key=lambda r: r.match.fit_score if r.match else -1, reverse=True)
    return rows


async def get_job_detail(db: AsyncSession, user_id: str, job_id: str) -> JobListingRow:
    job = await db.get(Job, job_id, options=[selectinload(Job.company), selectinload(Job.snapshots)])
    if job is None:
        raise NotFoundError("Job not found")

    match = await db.scalar(select(JobMatch).where(JobMatch.job_id == job_id, JobMatch.user_id == user_id))
    saved = await db.scalar(select(SavedJob).where(SavedJob.job_id == job_id, SavedJob.user_id == user_id))
    return JobListingRow(job=job, company=job.company, match=match, saved=saved)
