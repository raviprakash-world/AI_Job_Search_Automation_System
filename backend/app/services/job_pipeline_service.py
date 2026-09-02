from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.job_analysis_agent import analyze_job_posting
from app.core.errors import ExtractionValidationError
from app.core.logging import get_logger
from app.db.models import User
from app.schemas.jobs import DiscoveryResult
from app.services import job_discovery_service, matching_service

logger = get_logger(__name__)


async def run_discovery_and_match(db: AsyncSession, user: User, job_source) -> DiscoveryResult:
    outcome = await job_discovery_service.discover_jobs(db, job_source)

    for job in outcome.affected_jobs:
        if job.analysis_status != "pending":
            continue
        try:
            requirements, _ = await analyze_job_posting(
                db, user_id=user.id, title=job.title, description_text=job.description_text or ""
            )
            job.structured_requirements = requirements.model_dump(mode="json")
            job.analysis_status = "analyzed"
        except ExtractionValidationError as exc:
            job.analysis_status = "failed"
            logger.warning("job_analysis_failed", job_id=job.id, error=str(exc))
        await db.commit()

    matched = 0
    for job in outcome.affected_jobs:
        await matching_service.compute_match(db, user, job)
        matched += 1

    return DiscoveryResult(
        fetched=outcome.fetched,
        new_jobs=outcome.new_jobs,
        updated_jobs=outcome.updated_jobs,
        duplicates_merged=outcome.duplicates_merged,
        matched=matched,
    )
