from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job
from app.services.job_normalization import normalize_text

FUZZY_TITLE_THRESHOLD = 0.85


def find_matching_job(existing_jobs: list[Job], normalized_title: str, location_text: str | None) -> Job | None:
    """Deterministic + fuzzy duplicate detection within one company's jobs.

    Exact match on (normalized title, normalized location) wins first. Falling
    back to a title-similarity threshold catches minor wording variants (e.g.
    "Senior Software Engineer" vs "Sr. Software Engineer") without an AI call.
    Never merges across companies and never merges differing locations, to avoid
    collapsing genuinely distinct openings.
    """
    normalized_location = normalize_text(location_text or "")

    for job in existing_jobs:
        if job.normalized_title == normalized_title and normalize_text(job.location or "") == normalized_location:
            return job

    for job in existing_jobs:
        if normalize_text(job.location or "") != normalized_location:
            continue
        ratio = SequenceMatcher(None, job.normalized_title, normalized_title).ratio()
        if ratio >= FUZZY_TITLE_THRESHOLD:
            return job

    return None


async def find_existing_job(db: AsyncSession, *, company_id: str, normalized_title: str, location_text: str | None) -> Job | None:
    existing_jobs = list(await db.scalars(select(Job).where(Job.company_id == company_id)))
    return find_matching_job(existing_jobs, normalized_title, location_text)
