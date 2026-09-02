from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company, Job, JobSnapshot, JobSource
from app.providers.base import RawPosting
from app.providers.registry import get_provider
from app.services.audit_service import record_audit
from app.services.job_dedup_service import find_existing_job
from app.services.job_normalization import content_hash, html_to_text, infer_remote_status, normalize_text


@dataclass
class DiscoveryOutcome:
    fetched: int = 0
    new_jobs: int = 0
    updated_jobs: int = 0
    duplicates_merged: int = 0
    affected_jobs: list[Job] = field(default_factory=list)


async def _get_or_create_company(db: AsyncSession, name: str) -> Company:
    normalized = normalize_text(name)
    company = await db.scalar(select(Company).where(Company.normalized_name == normalized))
    if company is None:
        company = Company(name=name, normalized_name=normalized)
        db.add(company)
        await db.flush()
    return company


@dataclass
class _ApplyResult:
    job: Job
    is_new: bool
    is_changed: bool
    is_duplicate_merge: bool


async def _apply_posting(db: AsyncSession, job_source: JobSource, company: Company, posting: RawPosting) -> _ApplyResult:
    description_text = html_to_text(posting.content)
    new_hash = content_hash(description_text or posting.title)
    normalized_title = normalize_text(posting.title)

    existing_snapshot = await db.scalar(
        select(JobSnapshot).where(
            JobSnapshot.job_source_id == job_source.id,
            JobSnapshot.provider_job_id == posting.provider_job_id,
        )
    )

    if existing_snapshot is not None:
        job = await db.get(Job, existing_snapshot.job_id)
        existing_snapshot.raw_payload = posting.raw
        changed = job.content_hash != new_hash
        if changed:
            _update_job_fields(job, posting, description_text, new_hash, normalized_title)
        job.last_seen_at = existing_snapshot.fetched_at
        return _ApplyResult(job, is_new=False, is_changed=changed, is_duplicate_merge=False)

    duplicate = await find_existing_job(
        db, company_id=company.id, normalized_title=normalized_title, location_text=posting.location_text
    )
    if duplicate is not None:
        changed = duplicate.content_hash != new_hash
        if changed:
            _update_job_fields(duplicate, posting, description_text, new_hash, normalized_title)
        db.add(
            JobSnapshot(
                job_id=duplicate.id,
                job_source_id=job_source.id,
                provider_job_id=posting.provider_job_id,
                raw_payload=posting.raw,
            )
        )
        await db.flush()
        return _ApplyResult(duplicate, is_new=False, is_changed=changed, is_duplicate_merge=True)

    job = Job(
        company_id=company.id,
        title=posting.title,
        normalized_title=normalized_title,
        location=posting.location_text,
        remote_status=infer_remote_status(posting.location_text, posting.remote_flag, description_text),
        posting_url=posting.absolute_url,
        description_text=description_text,
        content_hash=new_hash,
        analysis_status="pending",
    )
    db.add(job)
    await db.flush()
    db.add(
        JobSnapshot(
            job_id=job.id, job_source_id=job_source.id, provider_job_id=posting.provider_job_id, raw_payload=posting.raw
        )
    )
    await db.flush()
    return _ApplyResult(job, is_new=True, is_changed=True, is_duplicate_merge=False)


def _update_job_fields(job: Job, posting: RawPosting, description_text: str, new_hash: str, normalized_title: str) -> None:
    job.title = posting.title
    job.normalized_title = normalized_title
    job.location = posting.location_text
    job.remote_status = infer_remote_status(posting.location_text, posting.remote_flag, description_text)
    job.posting_url = posting.absolute_url
    job.description_text = description_text
    job.content_hash = new_hash
    job.analysis_status = "pending"
    job.status = "open"


async def discover_jobs(db: AsyncSession, job_source: JobSource) -> DiscoveryOutcome:
    provider = get_provider(job_source.provider)
    postings = await provider.fetch_postings(job_source.company_slug)

    company_name = job_source.display_name or job_source.company_slug
    company = await _get_or_create_company(db, company_name)

    outcome = DiscoveryOutcome(fetched=len(postings))
    seen_job_ids: set[str] = set()

    for posting in postings:
        result = await _apply_posting(db, job_source, company, posting)
        if result.is_new:
            outcome.new_jobs += 1
        elif result.is_duplicate_merge:
            outcome.duplicates_merged += 1
        elif result.is_changed:
            outcome.updated_jobs += 1

        if result.job.id not in seen_job_ids and (result.is_new or result.is_changed):
            outcome.affected_jobs.append(result.job)
            seen_job_ids.add(result.job.id)

    job_source.last_polled_at = datetime.now(timezone.utc)

    await record_audit(
        db,
        user_id=job_source.user_id,
        entity_type="job_source",
        entity_id=job_source.id,
        action="discover",
        actor="system",
        after={
            "fetched": outcome.fetched,
            "new_jobs": outcome.new_jobs,
            "updated_jobs": outcome.updated_jobs,
        },
    )
    await db.commit()
    return outcome
